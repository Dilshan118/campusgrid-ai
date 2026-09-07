"""
CampusGrid AI: Telemetry & Forecasting Router (Agent 1)
Serves baseline historical meter intervals and 24-hour demand & solar PV forecasts.
"""

from fastapi import APIRouter, Depends, Query
from src.schemas.responses import APIResponse
from src.application.container import Container
from src.api.dependencies.container import get_app_container

router = APIRouter(prefix="/api/telemetry", tags=["Telemetry & Forecasting"])

@router.get("/historical", response_model=APIResponse)
async def get_historical_telemetry(
    date: str = Query(default="2026-09-06"),
    container: Container = Depends(get_app_container)
):
    intervals = container.meter_repo.get_historical_profile(date)
    return APIResponse(
        success=True,
        data=[item.model_dump() for item in intervals]
    )

@router.get("/forecast", response_model=APIResponse)
async def get_day_ahead_forecast(
    date: str = Query(default="2026-09-06"),
    room: str = Query(default="LH-1"),
    container: Container = Depends(get_app_container)
):
    res = container.agent1_telemetry.execute({"date": date, "room": room})
    return APIResponse(
        success=res.success,
        data=res.data,
        error=res.error,
        execution_time_ms=res.execution_time_ms
    )
