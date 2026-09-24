"""
CampusGrid AI: Authentication & User Session Router
Issues JWT access tokens and provides user role inspection.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from src.schemas.responses import APIResponse
from src.api.middleware.auth import (
    create_access_token,
    get_current_user,
    ROLE_FACILITY_MANAGER,
    ROLE_OPERATOR,
    ROLE_AUDITOR,
    AuthenticationError
)
from src.config.settings import get_settings

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
settings = get_settings()

DEMO_USERS = {
    "admin": {
        "password": "campusgrid2026",
        "role": ROLE_FACILITY_MANAGER,
        "full_name": "Chief Campus Energy Manager",
        "email": "director.energy@sliit.lk"
    },
    "operator": {
        "password": "operator123",
        "role": ROLE_OPERATOR,
        "full_name": "Substation Shift Operator",
        "email": "control.room@sliit.lk"
    },
    "auditor": {
        "password": "audit123",
        "role": ROLE_AUDITOR,
        "full_name": "PUCSL Compliance Auditor",
        "email": "auditor@pucsl.gov.lk"
    }
}


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponseData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str
    full_name: str
    expires_in_minutes: int


@router.post("/login", response_model=APIResponse)
async def login(request: LoginRequest):
    user = DEMO_USERS.get(request.username)
    if not user or user["password"] != request.password:
        raise AuthenticationError("Invalid username or password")

    token = create_access_token(user_id=request.username, role=user["role"])
    return APIResponse(
        success=True,
        data={
            "access_token": token,
            "token_type": "bearer",
            "user_id": request.username,
            "role": user["role"],
            "full_name": user["full_name"],
            "email": user["email"],
            "expires_in_minutes": settings.security.access_token_expire_minutes
        }
    )


@router.get("/me", response_model=APIResponse)
async def get_my_profile(current_user: Dict[str, Any] = Depends(get_current_user)):
    user_info = DEMO_USERS.get(current_user["user_id"], {
        "role": current_user.get("role", ROLE_OPERATOR),
        "full_name": current_user["user_id"].replace("_", " ").title(),
        "email": f"{current_user['user_id']}@campusgrid.local"
    })
    return APIResponse(
        success=True,
        data={
            "user_id": current_user["user_id"],
            "role": current_user["role"],
            "is_authenticated": current_user.get("is_authenticated", False),
            "full_name": user_info.get("full_name"),
            "email": user_info.get("email")
        }
    )


@router.get("/roles", response_model=APIResponse)
async def list_roles():
    return APIResponse(
        success=True,
        data={
            "roles": [
                {
                    "role": ROLE_FACILITY_MANAGER,
                    "description": "Full access to dispatch approval, optimization, simulation, and audit logs."
                },
                {
                    "role": ROLE_OPERATOR,
                    "description": "Can query orchestrator, run simulations, and review schedules."
                },
                {
                    "role": ROLE_AUDITOR,
                    "description": "Read-only access to immutable audit trails and compliance reports."
                }
            ]
        }
    )
