"""
CampusGrid AI: Web Analytics Router
Records dashboard interactions and serves the four analytics modules: query intent clusters,
the decision acceptance funnel (shown -> opened -> citation clicked -> decided), the XAI A/B
test, and citation click-through MRR.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends
from src.schemas.requests import AnalyticsEventRequest
from src.schemas.responses import APIResponse
from src.application.container import Container
from src.api.dependencies.container import get_app_container
from src.api.middleware.auth import require_roles, ALL_ROLES, ROLES_ANALYTICS_VIEWERS
from src.domain.entities.analytics import AnalyticsEvent, CLIENT_EVENT_TYPES
from src.domain.exceptions.base import DomainException

router = APIRouter(prefix="/api/analytics", tags=["Web Analytics"])

@router.post("/event", response_model=APIResponse)
async def record_funnel_event(
    request: AnalyticsEventRequest,
    user: Dict[str, Any] = Depends(require_roles(ALL_ROLES)),
    container: Container = Depends(get_app_container)
):
    # Decisions and queries are logged by the server itself, so the browser cannot forge them.
    if request.event_type not in CLIENT_EVENT_TYPES:
        raise DomainException(
            message=f"Unsupported event_type '{request.event_type}'. Allowed: {sorted(CLIENT_EVENT_TYPES)}",
            error_code="VALIDATION_ERROR",
            details={"status": 422, "field": "event_type"},
        )
    event_id = container.analytics_service.track(AnalyticsEvent(
        event_type=request.event_type,
        user_id=user["user_id"],
        role=user["role"],
        session_id=request.session_id,
        audit_log_id=request.audit_log_id,
        query_text=request.query_text,
        rank=request.rank,
        clause_reference=request.clause_reference,
    ))
    return APIResponse(success=True, data={"event_id": event_id})

@router.get("/ab/assignment", response_model=APIResponse)
async def get_my_ab_variant(
    user: Dict[str, Any] = Depends(require_roles(ALL_ROLES)),
    container: Container = Depends(get_app_container)
):
    return APIResponse(success=True, data={"ab_variant": container.analytics_service.assign_variant(user["user_id"])})

@router.get("/summary", response_model=APIResponse)
async def get_analytics_summary(
    _user=Depends(require_roles(ROLES_ANALYTICS_VIEWERS)),
    container: Container = Depends(get_app_container)
):
    return APIResponse(success=True, data=container.analytics_service.summary())

@router.get("/funnel", response_model=APIResponse)
async def get_acceptance_funnel(
    _user=Depends(require_roles(ROLES_ANALYTICS_VIEWERS)),
    container: Container = Depends(get_app_container)
):
    return APIResponse(success=True, data=container.analytics_service.acceptance_funnel())

@router.get("/ab-test", response_model=APIResponse)
async def get_ab_test_results(
    _user=Depends(require_roles(ROLES_ANALYTICS_VIEWERS)),
    container: Container = Depends(get_app_container)
):
    return APIResponse(success=True, data=container.analytics_service.ab_test())

@router.get("/query-clusters", response_model=APIResponse)
async def get_query_clusters(
    _user=Depends(require_roles(ROLES_ANALYTICS_VIEWERS)),
    container: Container = Depends(get_app_container)
):
    return APIResponse(success=True, data=container.analytics_service.query_clusters())

@router.get("/citation-ctr", response_model=APIResponse)
async def get_citation_click_through(
    _user=Depends(require_roles(ROLES_ANALYTICS_VIEWERS)),
    container: Container = Depends(get_app_container)
):
    return APIResponse(success=True, data=container.analytics_service.citation_click_through())
