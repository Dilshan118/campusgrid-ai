"""
CampusGrid AI: Timetable Router
The semester teaching timetable that sets expected room occupancy. There is no live feed: the
faculty timetable office uploads it as CSV, or adds and removes single sessions.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Query
from src.schemas.requests import TimetableUploadRequest, TimetableSessionRequest
from src.schemas.responses import APIResponse
from src.application.container import Container
from src.api.dependencies.container import get_app_container
from src.api.middleware.auth import require_roles, ROLES_TIMETABLE_MANAGERS, ROLES_TIMETABLE_READERS

router = APIRouter(prefix="/api/timetable", tags=["Timetable"])


@router.get("", response_model=APIResponse)
def list_timetable(
    day: Optional[int] = Query(default=None, ge=1, le=7, description="1 = Monday ... 7 = Sunday"),
    _user=Depends(require_roles(ROLES_TIMETABLE_READERS)),
    container: Container = Depends(get_app_container),
):
    return APIResponse(success=True, data=container.timetable_service.list_entries(day))


@router.post("/upload", response_model=APIResponse)
def upload_timetable(
    request: TimetableUploadRequest,
    user: Dict[str, Any] = Depends(require_roles(ROLES_TIMETABLE_MANAGERS)),
    container: Container = Depends(get_app_container),
):
    """Validate (dry_run=true) or apply a CSV timetable. Applying is all-or-nothing."""
    return APIResponse(success=True, data=container.timetable_service.upload_csv(
        csv_text="\n".join(request.csv_lines),
        mode=request.mode,
        user_id=user["user_id"],
        dry_run=request.dry_run,
        filename=request.filename,
    ))


@router.post("/sessions", response_model=APIResponse)
def add_session(
    request: TimetableSessionRequest,
    user: Dict[str, Any] = Depends(require_roles(ROLES_TIMETABLE_MANAGERS)),
    container: Container = Depends(get_app_container),
):
    return APIResponse(success=True, data=container.timetable_service.add_session(request.model_dump(), user["user_id"]))


@router.delete("/sessions/{schedule_id}", response_model=APIResponse)
def delete_session(
    schedule_id: int,
    user: Dict[str, Any] = Depends(require_roles(ROLES_TIMETABLE_MANAGERS)),
    container: Container = Depends(get_app_container),
):
    return APIResponse(success=True, data=container.timetable_service.delete_session(schedule_id, user["user_id"]))
