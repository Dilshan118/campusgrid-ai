"""
CampusGrid AI: Authentication & User Session Router
Issues JWT access tokens, revokes them on logout, and exposes the caller's profile and permissions.
"""

from typing import Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends
from src.schemas.responses import APIResponse
from src.api.middleware.auth import (
    create_access_token,
    get_current_user,
    verify_password,
    login_throttle,
    revoke_token,
    ROLE_FACILITY_MANAGER,
    ROLE_OPERATOR,
    ROLE_AUDITOR,
    AuthenticationError,
)
from src.config.settings import get_settings

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
settings = get_settings()

# Demo accounts for the coursework build. Passwords are stored only as PBKDF2 hashes;
# the plaintext demo credentials are documented in README.md. A production deployment
# replaces this dictionary with the university's identity provider.
DEMO_USERS = {
    "admin": {
        "password_hash": "pbkdf2_sha256$120000$76a3449e3602f57fa65821dd77f05831$759869f77ec8b254202665b0def073fe988c8f67051fbea073c6f3f13e655bcb",
        "role": ROLE_FACILITY_MANAGER,
        "full_name": "Chief Campus Energy Manager",
    },
    "operator": {
        "password_hash": "pbkdf2_sha256$120000$d0494fed60468a9157ccdab7b0dbd963$3c3a33578df0b07dfe3d789cfc1f8a5ad8a423b116cc64e90f8b4a7928402095",
        "role": ROLE_OPERATOR,
        "full_name": "Substation Shift Operator",
    },
    "auditor": {
        "password_hash": "pbkdf2_sha256$120000$f3b40d8aebd26b89018808fb5576795e$9fb0f11ff13da0c354ec3d6748a7e41deffd724eef00d67978f4519852941fee",
        "role": ROLE_AUDITOR,
        "full_name": "PUCSL Compliance Auditor",
    },
}

# What each role may do, so the dashboard can hide actions instead of letting users hit 403s.
ROLE_PERMISSIONS = {
    ROLE_FACILITY_MANAGER: {
        "description": "Full access: plans, simulations, dispatch approval, knowledge base management, analytics and audit.",
        "permissions": [
            "orchestrator:query", "simulation:run", "optimizer:run", "telemetry:read",
            "rag:search", "rag:ingest", "audit:read", "audit:approve", "analytics:read", "system:read",
        ],
    },
    ROLE_OPERATOR: {
        "description": "Day-to-day operation: queries, simulations and dispatch plans. Cannot approve plans.",
        "permissions": [
            "orchestrator:query", "simulation:run", "optimizer:run", "telemetry:read",
            "rag:search", "audit:read",
        ],
    },
    ROLE_AUDITOR: {
        "description": "Read-only compliance access to the audit trail, regulations and analytics.",
        "permissions": ["rag:search", "audit:read", "analytics:read"],
    },
}

# Identical work on unknown usernames so response time does not reveal which accounts exist.
_DUMMY_HASH = DEMO_USERS["operator"]["password_hash"]


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


@router.post("/login", response_model=APIResponse)
def login(request: LoginRequest):
    username = request.username.strip().lower()
    login_throttle.check(username)

    user = DEMO_USERS.get(username)
    password_ok = verify_password(request.password, user["password_hash"] if user else _DUMMY_HASH)
    if not user or not password_ok:
        login_throttle.record_failure(username)
        raise AuthenticationError("Invalid username or password")

    login_throttle.record_success(username)
    token = create_access_token(user_id=username, role=user["role"])
    return APIResponse(
        success=True,
        data={
            "access_token": token,
            "token_type": "bearer",
            "user_id": username,
            "role": user["role"],
            "full_name": user["full_name"],
            "permissions": ROLE_PERMISSIONS[user["role"]]["permissions"],
            "expires_in_minutes": settings.security.access_token_expire_minutes
        }
    )


@router.post("/logout", response_model=APIResponse)
def logout(current_user: Dict[str, Any] = Depends(get_current_user)):
    if current_user.get("jti"):
        revoke_token(current_user["jti"], float(current_user.get("exp") or 0))
    return APIResponse(success=True, data={"logged_out": True})


@router.get("/me", response_model=APIResponse)
def get_my_profile(current_user: Dict[str, Any] = Depends(get_current_user)):
    user_info = DEMO_USERS.get(current_user["user_id"], {})
    role = current_user["role"]
    return APIResponse(
        success=True,
        data={
            "user_id": current_user["user_id"],
            "role": role,
            "is_authenticated": True,
            "full_name": user_info.get("full_name", current_user["user_id"]),
            "permissions": ROLE_PERMISSIONS[role]["permissions"],
        }
    )


@router.get("/roles", response_model=APIResponse)
def list_roles(_user: Dict[str, Any] = Depends(get_current_user)):
    return APIResponse(
        success=True,
        data={
            "roles": [
                {"role": role, **details} for role, details in ROLE_PERMISSIONS.items()
            ]
        }
    )
