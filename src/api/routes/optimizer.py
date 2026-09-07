"""
CampusGrid AI: Dispatch Optimizer Router (Agent 4)
Solves 48-interval microgrid dispatch and returns optimal battery schedules and savings.
"""

from fastapi import APIRouter, Depends
from src.schemas.requests import OptimizationRunRequest
from src.schemas.responses import APIResponse
from src.application.container import Container
from src.api.dependencies.container import get_app_container

router = APIRouter(prefix="/api/optimizer", tags=["Dispatch Optimizer"])

@router.post("/dispatch", response_model=APIResponse)
async def solve_dispatch(
    request: OptimizationRunRequest,
    container: Container = Depends(get_app_container)
):
    # Fetch historical benchmark profile
    historical = container.meter_repo.get_historical_profile("2026-09-06")

    time_slots = [item.time_slot for item in historical]
    base_load = [item.base_load_kw for item in historical]
    solar_gen = [item.solar_gen_kw for item in historical]
    tariffs = [item.grid_tariff_lkr_kwh for item in historical]

    res = container.agent4_dispatch.execute({
        "time_slots": time_slots,
        "forecast_demand_kw": base_load,
        "forecast_solar_kw": solar_gen,
        "tariffs_lkr_kwh": tariffs,
        "user_query": "Solve 48-period battery dispatch to shave peak demand."
    })

    return APIResponse(
        success=res.success,
        data=res.data,
        error=res.error,
        execution_time_ms=res.execution_time_ms
    )
