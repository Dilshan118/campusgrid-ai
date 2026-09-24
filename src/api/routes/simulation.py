"""
CampusGrid AI: Digital Twin Simulation Router (Agent 2)
Provides what-if simulation and thermal dynamics evaluation.
"""

from fastapi import APIRouter, Depends
from src.schemas.requests import WhatIfSimulationRequest
from src.schemas.responses import APIResponse
from src.application.container import Container
from src.api.dependencies.container import get_app_container
from src.api.middleware.auth import require_roles, ROLES_PLANNERS
from src.api.routes.common import agent_response, default_planning_date

router = APIRouter(prefix="/api/simulation", tags=["Digital Twin Simulation"])

@router.post("/what-if", response_model=APIResponse)
def run_what_if_simulation(
    request: WhatIfSimulationRequest,
    _user=Depends(require_roles(ROLES_PLANNERS)),
    container: Container = Depends(get_app_container)
):
    target_date = default_planning_date(request.date)
    physics = container.settings.physics

    weather_res = container.weather_tool.execute(date=target_date)
    ambients = weather_res.data.get("temperature_series_c", [28.0] * 48)

    historical = container.meter_repo.get_historical_profile(target_date)
    occupancies, capped, capacity = container.orchestrator.room_level_occupancy(
        request.room, [item.zone_occupancy_count for item in historical]
    )

    res = container.agent2_twin.execute({
        "initial_temp_c": request.initial_temp_c,
        "ambient_temperatures_c": ambients,
        "occupancy_counts": occupancies,
        "perturb_temp_delta_c": request.ambient_temp_delta_c,
        "perturb_occ_multiplier": request.occupancy_multiplier,
        "comfort_min_c": physics.comfort_min_temp_c,
        "comfort_max_c": physics.comfort_max_temp_c,
    })
    response = agent_response(res)
    response.data["weather_source"] = weather_res.data.get("source")
    response.data["target_date"] = target_date
    response.data["room"] = request.room.upper()
    response.data["occupancy_capped_intervals"] = capped
    response.data["room_capacity"] = capacity
    return response
