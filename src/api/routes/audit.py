"""
CampusGrid AI: Audit Trail Router
Read access to the append-only audit trail, the pending-approval queue, the human approval
decision itself, and verification of the tamper-evident hash chain.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Query
from src.schemas.requests import AuditApprovalRequest
from src.schemas.responses import APIResponse
from src.application.container import Container
from src.api.dependencies.container import get_app_container
from src.api.middleware.auth import require_roles, ALL_ROLES, ROLES_APPROVERS, ROLES_ANALYTICS_VIEWERS
from src.domain.entities.analytics import AnalyticsEvent, EVENT_DECISION_APPROVED, EVENT_DECISION_REJECTED

router = APIRouter(prefix="/api/audit", tags=["Audit Trail"])

@router.get("/logs", response_model=APIResponse)
def list_audit_logs(
    limit: int = Query(default=20, ge=1, le=100),
    record_type: Optional[str] = Query(default=None, max_length=40),
    status: Optional[str] = Query(default=None, max_length=20),
    include_details: bool = Query(default=False, description="Include the full per-agent outputs"),
    _user=Depends(require_roles(ALL_ROLES)),
    container: Container = Depends(get_app_container)
):
    return APIResponse(
        success=True,
        data=container.audit_service.list_views(
            limit=limit, record_type=record_type, status=status, include_agent_sequence=include_details
        )
    )

@router.get("/logs/{log_id}", response_model=APIResponse)
def get_audit_log(
    log_id: int,
    include_details: bool = Query(default=True, description="Include the full per-agent outputs"),
    _user=Depends(require_roles(ALL_ROLES)),
    container: Container = Depends(get_app_container)
):
    return APIResponse(
        success=True,
        data=container.audit_service.get_record_view(log_id, include_agent_sequence=include_details),
    )

@router.get("/pending", response_model=APIResponse)
def list_pending_recommendations(
    limit: int = Query(default=20, ge=1, le=100),
    _user=Depends(require_roles(ALL_ROLES)),
    container: Container = Depends(get_app_container)
):
    return APIResponse(success=True, data=container.audit_service.list_pending(limit=limit))

@router.post("/approve", response_model=APIResponse)
def decide_recommendation(
    request: AuditApprovalRequest,
    user: Dict[str, Any] = Depends(require_roles(ROLES_APPROVERS)),
    container: Container = Depends(get_app_container)
):
    """Approve or reject a pending dispatch recommendation (facility managers only).

    Appends a signed decision record; the recommendation itself is never modified.
    Nothing is actuated by this call — CampusGrid AI is advisory.
    """
    decision = container.audit_service.record_decision(
        log_id=request.log_id,
        approver_id=user["user_id"],
        approved=request.approved,
        notes=request.operator_notes,
        acknowledge_warnings=request.acknowledge_warnings,
    )
    container.analytics_service.track(AnalyticsEvent(
        event_type=EVENT_DECISION_APPROVED if request.approved else EVENT_DECISION_REJECTED,
        user_id=user["user_id"],
        role=user["role"],
        audit_log_id=request.log_id,
    ))
    return APIResponse(success=True, data=decision)

@router.get("/verify", response_model=APIResponse)
def verify_audit_chain(
    _user=Depends(require_roles(ROLES_ANALYTICS_VIEWERS)),
    container: Container = Depends(get_app_container)
):
    return APIResponse(success=True, data=container.audit_service.verify_chain())
