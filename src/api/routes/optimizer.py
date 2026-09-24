"""
CampusGrid AI: Dispatch Optimizer Router (Agent 4)
Solves 48-interval microgrid dispatch and returns optimal battery schedules and savings.

A dispatch plan is only ever produced through the orchestrator, so the solver always receives
Agent 1's forecast and Agent 3's retrieved tariff, and every plan lands in the audit trail as a
pending recommendation that a facility manager must approve.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends
from src.schemas.requests import OptimizationRunRequest
from src.schemas.responses import APIResponse
from src.application.container import Container
from src.api.dependencies.container import get_app_container
from src.api.middleware.auth import require_roles, ROLES_PLANNERS
from src.api.routes.common import agent_response, default_planning_date

router = APIRouter(prefix="/api/optimizer", tags=["Dispatch Optimizer"])

@router.post("/dispatch", response_model=APIResponse)
async def solve_dispatch(
    request: OptimizationRunRequest,
    user: Dict[str, Any] = Depends(require_roles(ROLES_PLANNERS)),
    container: Container = Depends(get_app_container)
):
    target_date = default_planning_date(request.date)
    res = container.orchestrator.execute({
        "query": f"Optimize battery dispatch for {request.room} on {target_date} to minimize the peak demand charge.",
        "user_id": user["user_id"],
        "force_full_pipeline": True,
        "room": request.room,
        "date": target_date,
        "battery_parameters": {
            "battery_capacity_kwh": request.battery_capacity_kwh,
            "max_charge_rate_kw": request.max_charge_rate_kw,
            "max_discharge_rate_kw": request.max_discharge_rate_kw,
            "initial_soc_ratio": request.initial_soc_ratio,
        },
    })
    response = agent_response(res)
    # Flat fields kept for existing clients of this endpoint.
    rec = response.data.get("recommendation", {})
    response.data.update({
        "solver_output": rec.get("solver_summary", {}),
        "net_savings_lkr": rec.get("net_savings_lkr"),
        "savings_percentage": rec.get("savings_percentage"),
        "peak_shaved_kw": rec.get("peak_shaved_kw"),
    })
    return response
