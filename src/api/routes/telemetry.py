"""
CampusGrid AI: Telemetry & Forecasting Router (Agent 1)
Serves baseline historical meter intervals and 24-hour demand & solar PV forecasts.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Query, Response
from src.schemas.responses import APIResponse
from src.application.container import Container
from src.api.dependencies.container import get_app_container
from src.api.middleware.auth import require_roles, ROLES_FORECAST_READERS
from src.api.middleware.rate_limit import limit_planner_requests
from src.api.routes.common import agent_response, default_planning_date, default_history_date
from src.schemas.requests import ISO_DATE_PATTERN
from src.domain.entities.audit import RECORD_FORECAST_REVIEW

router = APIRouter(prefix="/api/telemetry", tags=["Telemetry & Forecasting"])

PRIVACY_EPSILON = 1.0

@router.get("/historical", response_model=APIResponse)
def get_historical_telemetry(
    response: Response,
    date: Optional[str] = Query(default=None, pattern=ISO_DATE_PATTERN, description="Defaults to yesterday"),
    _user=Depends(require_roles(ROLES_FORECAST_READERS)),
    container: Container = Depends(get_app_container)
):
    date = default_history_date(date)
    # Leaves the backend, so it carries Laplace differential-privacy noise (Agent 1's export path),
    # never the exact sub-meter readings that enable NILM-style disaggregation.
    intervals = container.agent1_telemetry.get_privacy_protected_export(date, epsilon=PRIVACY_EPSILON)
    response.headers["X-Privacy-Mechanism"] = f"laplace;epsilon={PRIVACY_EPSILON}"
    return APIResponse(
        success=True,
        data=[item.model_dump() for item in intervals]
    )

@router.get("/forecast", response_model=APIResponse, dependencies=[Depends(limit_planner_requests)])
def get_day_ahead_forecast(
    date: Optional[str] = Query(default=None, pattern=ISO_DATE_PATTERN, description="Defaults to tomorrow"),
    room: str = Query(default="LH-1", max_length=20),
    user: Dict[str, Any] = Depends(require_roles(ROLES_FORECAST_READERS)),
    container: Container = Depends(get_app_container)
):
    target_date = default_planning_date(date)
    res = container.agent1_telemetry.execute({"date": target_date, "room": room})
    response = agent_response(res)
    # Same record the Ask CampusGrid forecast branch writes, so every forecast shown is on the audit trail.
    demand = res.data.get("forecast_demand_kw") or []
    response.data["audit_log_id"] = container.audit_service.log_operator_action(
        user_id=user["user_id"],
        query=f"Forecast page: {target_date}, room {room}",
        agent_sequence={"agent1_telemetry": res.model_dump()},
        decision={
            "summary": "Day-ahead demand and solar forecast (Forecast page).",
            "target_date": target_date,
            "room": room,
            "peak_demand_kw": max(demand) if demand else None,
            "anomaly_count": res.data.get("anomaly_count", 0),
            "data_sources": res.data.get("data_sources"),
        },
        record_type=RECORD_FORECAST_REVIEW,
    )
    return response
