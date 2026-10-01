"""
CampusGrid AI: Digital Twin Simulation Router (Agent 2)
Provides what-if simulation and thermal dynamics evaluation.
"""

from datetime import date
from typing import Any, Dict

from fastapi import APIRouter, Depends
from src.schemas.requests import WhatIfSimulationRequest
from src.schemas.responses import APIResponse
from src.application.container import Container
from src.api.dependencies.container import get_app_container
from src.api.middleware.auth import require_roles, ROLES_PLANNERS
from src.api.routes.common import agent_response, default_planning_date
from src.agents.digital_twin.room_presets import build_venue_catalogue
from src.agents.digital_twin.operating_hours import describe_operating_hours, occupied_mask, operating_hours_for
from src.domain.exceptions.base import EntityNotFoundError
from src.domain.entities.audit import RECORD_WHAT_IF_SIMULATION
from src.shared.datetime_utils import campus_today

router = APIRouter(prefix="/api/simulation", tags=["Digital Twin Simulation"])


@router.get("/venues", response_model=APIResponse)
def list_venues(
    _user=Depends(require_roles(ROLES_PLANNERS)),
    container: Container = Depends(get_app_container),
):
    """Venue types (with the listed rooms of each type), campus operating hours, and the
    campus date the simulator treats as "today" — everything the what-if form needs."""
    return APIResponse(success=True, data={
        "venue_types": build_venue_catalogue(container.room_repo.list_all()),
        "operating_hours": describe_operating_hours(),
        "today": campus_today().isoformat(),
    })


@router.post("/what-if", response_model=APIResponse)
def run_what_if_simulation(
    request: WhatIfSimulationRequest,
    user: Dict[str, Any] = Depends(require_roles(ROLES_PLANNERS)),
    container: Container = Depends(get_app_container)
):
    target_date = default_planning_date(request.date)
    physics = container.settings.physics

    weather_res = container.weather_tool.execute(date=target_date)
    ambients = weather_res.data.get("temperature_series_c", [28.0] * 48)

    hours = operating_hours_for(date.fromisoformat(target_date))

    if request.room_type:
        # A room that is not in the campus inventory: the caller describes it.
        room_id, building_name = None, None
        room_type, capacity, num_acs = request.room_type, request.seating_capacity, request.num_acs
    else:
        room_id = request.room.strip().upper()
        room = container.room_repo.get_by_id(room_id)
        if room is None:
            raise EntityNotFoundError("Room", room_id)
        building_name = room.get("building_name")
        room_type, capacity, num_acs = room["room_type"], room["max_capacity"], None

    res = container.agent2_twin.execute({
        "initial_temp_c": request.initial_temp_c,
        "ambient_temperatures_c": ambients,
        "perturb_temp_delta_c": request.ambient_temp_delta_c,
        "perturb_occ_multiplier": request.occupancy_multiplier,
        "comfort_min_c": physics.comfort_min_temp_c,
        "comfort_max_c": physics.comfort_max_temp_c,
        "room_type": room_type,
        "seating_capacity": capacity,
        "num_acs": num_acs,
        "occupied_mask": occupied_mask(hours, len(ambients)),
        "precool_intervals": request.precool_minutes // 30,
        "date": target_date,  # the sun's path for the room's solar heat gain
    })
    response = agent_response(res)
    room_config = response.data.get("room_config") or {}
    response.data["weather_source"] = weather_res.data.get("source")
    response.data["target_date"] = target_date
    response.data["operating_hours"] = hours.as_dict()
    response.data["room"] = room_id or f"Custom {room_config.get('label', 'room')}"
    response.data["building_name"] = building_name
    response.data["is_custom_room"] = room_id is None
    response.data["room_capacity"] = room_config.get("capacity", capacity)
    # Occupancy now comes from the room's own seats and operating hours, not the
    # building-wide meter, so nothing is capped any more; kept for API compatibility.
    response.data["occupancy_capped_intervals"] = 0
    # Same record the Ask CampusGrid simulation branch writes, so every simulation shown is on the audit trail.
    response.data["audit_log_id"] = container.audit_service.log_operator_action(
        user_id=user["user_id"],
        query=f"What-if simulator: {response.data['room']} on {target_date}",
        agent_sequence={"agent2_digital_twin": res.model_dump()},
        decision={
            "summary": "What-if simulation (What-if simulator page).",
            "target_date": target_date,
            "room": response.data["room"],
            "inputs": request.model_dump(),
            "is_thermal_feasible": res.data.get("is_thermal_feasible"),
            "comfort_violations_count": res.data.get("comfort_violations_count"),
            "weather_source": response.data["weather_source"],
        },
        record_type=RECORD_WHAT_IF_SIMULATION,
    )
    return response
