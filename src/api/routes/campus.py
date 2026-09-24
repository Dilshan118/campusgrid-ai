"""
CampusGrid AI: Campus Inventory Router
The room / zone inventory that pickers in the dashboard offer. Contains no personal data.
"""

from fastapi import APIRouter, Depends
from src.schemas.responses import APIResponse
from src.application.container import Container
from src.api.dependencies.container import get_app_container
from src.api.middleware.auth import require_roles, ALL_ROLES

router = APIRouter(prefix="/api/campus", tags=["Campus Inventory"])

@router.get("/rooms", response_model=APIResponse)
def list_rooms(
    _user=Depends(require_roles(ALL_ROLES)),
    container: Container = Depends(get_app_container)
):
    return APIResponse(success=True, data=container.nlp_parser_rooms())
