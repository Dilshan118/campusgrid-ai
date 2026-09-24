"""
CampusGrid AI: Orchestrator Router
Runs the full multi-agent sequential pipeline: Query -> A1 -> A2 -> A3 -> A4 -> Approval Queue.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends
from src.schemas.requests import OperatorQueryRequest
from src.schemas.responses import APIResponse
from src.application.container import Container
from src.api.dependencies.container import get_app_container
from src.api.middleware.auth import require_roles, ROLES_PLANNERS
from src.api.routes.common import agent_response
from src.domain.entities.analytics import AnalyticsEvent, EVENT_QUERY_SUBMITTED

router = APIRouter(prefix="/api/orchestrator", tags=["Multi-Agent Orchestrator"])

@router.post("/query", response_model=APIResponse)
async def process_operator_query(
    request: OperatorQueryRequest,
    user: Dict[str, Any] = Depends(require_roles(ROLES_PLANNERS)),
    container: Container = Depends(get_app_container)
):
    res = container.orchestrator.execute({
        "query": request.query,
        # The acting user always comes from the verified token, never from the request body,
        # so the audit trail cannot be attributed to someone else.
        "user_id": user["user_id"],
        "session_id": request.session_id,
        "perturb_temp_delta_c": request.perturb_temp_delta_c,
        "perturb_occ_multiplier": request.perturb_occ_multiplier
    })
    response = agent_response(res)

    variant = container.analytics_service.assign_variant(user["user_id"])
    response.data["ab_variant"] = variant
    parsed = response.data.get("parsed_intent", {})
    container.analytics_service.track(AnalyticsEvent(
        event_type=EVENT_QUERY_SUBMITTED,
        user_id=user["user_id"],
        role=user["role"],
        session_id=response.data.get("session_id"),
        audit_log_id=response.data.get("audit_log_id"),
        ab_variant=variant,
        intent=parsed.get("action"),
        query_text=request.query[:500],
    ))
    return response
