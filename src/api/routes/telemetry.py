"""
CampusGrid AI: Telemetry & Forecasting Router (Agent 1)
Serves baseline historical meter intervals and 24-hour demand & solar PV forecasts.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Response
from src.schemas.responses import APIResponse
from src.application.container import Container
from src.api.dependencies.container import get_app_container
from src.api.middleware.auth import require_roles, ROLES_PLANNERS
from src.api.routes.common import agent_response, default_planning_date

router = APIRouter(prefix="/api/telemetry", tags=["Telemetry & Forecasting"])

PRIVACY_EPSILON = 1.0

@router.get("/historical", response_model=APIResponse)
async def get_historical_telemetry(
    response: Response,
    date: str = Query(default="2026-09-06", max_length=10),
    _user=Depends(require_roles(ROLES_PLANNERS)),
    container: Container = Depends(get_app_container)
):
    # Leaves the backend, so it carries Laplace differential-privacy noise (Agent 1's export path),
    # never the exact sub-meter readings that enable NILM-style disaggregation.
    intervals = container.agent1_telemetry.get_privacy_protected_export(date, epsilon=PRIVACY_EPSILON)
    response.headers["X-Privacy-Mechanism"] = f"laplace;epsilon={PRIVACY_EPSILON}"
    return APIResponse(
        success=True,
        data=[item.model_dump() for item in intervals]
    )

@router.get("/forecast", response_model=APIResponse)
async def get_day_ahead_forecast(
    date: Optional[str] = Query(default=None, max_length=10),
    room: str = Query(default="LH-1", max_length=20),
    _user=Depends(require_roles(ROLES_PLANNERS)),
    container: Container = Depends(get_app_container)
):
    res = container.agent1_telemetry.execute({"date": default_planning_date(date), "room": room})
    return agent_response(res)
