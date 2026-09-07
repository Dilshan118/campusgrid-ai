"""
CampusGrid AI: Audit Trail Router
Provides read access to the append-only audit trail and human approval records.
"""

from fastapi import APIRouter, Depends, Query
from src.schemas.responses import APIResponse
from src.application.container import Container
from src.api.dependencies.container import get_app_container

router = APIRouter(prefix="/api/audit", tags=["Audit Trail"])

@router.get("/logs", response_model=APIResponse)
async def list_audit_logs(
    limit: int = Query(default=20, ge=1, le=100),
    container: Container = Depends(get_app_container)
):
    records = container.audit_service.get_audit_trail(limit=limit)
    return APIResponse(
        success=True,
        data=[r.model_dump() for r in records]
    )
