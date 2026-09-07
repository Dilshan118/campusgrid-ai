"""
CampusGrid AI: Digital Twin Simulation Router (Agent 2)
Provides what-if simulation and thermal dynamics evaluation.
"""

from fastapi import APIRouter, Depends
from src.schemas.requests import WhatIfSimulationRequest
from src.schemas.responses import APIResponse
from src.application.container import Container
from src.api.dependencies.container import get_app_container

router = APIRouter(prefix="/api/simulation", tags=["Digital Twin Simulation"])

@router.post("/what-if", response_model=APIResponse)
async def run_what_if_simulation(
    request: WhatIfSimulationRequest,
    container: Container = Depends(get_app_container)
):
    # Fetch base ambient series from weather tool
    weather_res = container.weather_tool.execute()
    ambients = weather_res.data.get("temperature_series_c", [28.0] * 48)

    # Fetch baseline occupancies
    historical = container.meter_repo.get_historical_profile("2026-09-06")
    occupancies = [item.zone_occupancy_count for item in historical]

    res = container.agent2_twin.execute({
        "initial_temp_c": request.initial_temp_c,
        "ambient_temperatures_c": ambients,
        "occupancy_counts": occupancies,
        "perturb_temp_delta_c": request.ambient_temp_delta_c,
        "perturb_occ_multiplier": request.occupancy_multiplier
    })

    return APIResponse(
        success=res.success,
        data=res.data,
        error=res.error,
        execution_time_ms=res.execution_time_ms
    )
