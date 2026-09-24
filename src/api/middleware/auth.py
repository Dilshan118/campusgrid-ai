"""
CampusGrid AI: Authentication & RBAC Security Middleware
JWT token generation, role-based access control, and user session verification.

Every protected route declares the roles it accepts with `Depends(require_roles(...))`.
There is no anonymous fallback: a request without a valid bearer token is rejected
with HTTP 401, and a valid token whose role is not allowed is rejected with HTTP 403.
"""

import hashlib
import hmac
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
import jwt
from fastapi import Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.config.settings import get_settings
from src.domain.exceptions.base import DomainException

settings = get_settings()
security = HTTPBearer(auto_error=False)

TOKEN_ISSUER = "campusgrid-ai-auth"

ROLE_FACILITY_MANAGER = "FACILITY_MANAGER"
ROLE_OPERATOR = "OPERATOR"
ROLE_AUDITOR = "ENERGY_AUDITOR"

ALL_ROLES = [ROLE_FACILITY_MANAGER, ROLE_OPERATOR, ROLE_AUDITOR]

# Role groups, so every route states its permission in one readable word.
ROLES_PLANNERS = [ROLE_FACILITY_MANAGER, ROLE_OPERATOR]        # run queries, simulations, dispatch
ROLES_APPROVERS = [ROLE_FACILITY_MANAGER]                      # approve / reject recommendations
ROLES_KNOWLEDGE_ADMINS = [ROLE_FACILITY_MANAGER]               # ingest regulatory documents
ROLES_ANALYTICS_VIEWERS = [ROLE_FACILITY_MANAGER, ROLE_AUDITOR]


class AuthenticationError(DomainException):
    def __init__(self, message: str = "Invalid or expired authentication credentials"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_FAILED",
            details={"status": 401}
        )


class AuthorizationError(DomainException):
    def __init__(self, message: str = "Insufficient permissions for requested resource"):
        super().__init__(
            message=message,
            error_code="PERMISSION_DENIED",
            details={"status": 403}
        )


class AccountLockedError(DomainException):
    def __init__(self, retry_after_seconds: int):
        super().__init__(
            message="Too many failed login attempts. Try again later.",
            error_code="ACCOUNT_TEMPORARILY_LOCKED",
            details={"status": 429, "retry_after_seconds": retry_after_seconds}
        )


# ---------------------------------------------------------------------------
# Password hashing (PBKDF2-SHA256, stdlib only)
# ---------------------------------------------------------------------------

def hash_password(password: str, salt_hex: str, iterations: int = 120_000) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), iterations)
    return f"pbkdf2_sha256${iterations}${salt_hex}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Constant-time comparison against a 'pbkdf2_sha256$iter$salt$hash' string."""
    try:
        _, iterations, salt_hex, _ = stored_hash.split("$")
        candidate = hash_password(password, salt_hex, int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, stored_hash)


# ---------------------------------------------------------------------------
# Brute-force throttle and token revocation (in-process; single-instance deployment)
# ---------------------------------------------------------------------------

class LoginThrottle:
    """Locks a username for a cooling-off period after repeated failed logins."""

    def __init__(self, max_attempts: int, lockout_seconds: int):
        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds
        self._failures: Dict[str, List[float]] = {}
        self._locked_until: Dict[str, float] = {}
        self._lock = threading.Lock()

    def check(self, username: str) -> None:
        with self._lock:
            until = self._locked_until.get(username, 0.0)
            if until > time.time():
                raise AccountLockedError(retry_after_seconds=int(until - time.time()) + 1)

    def record_failure(self, username: str) -> None:
        now = time.time()
        with self._lock:
            window = [t for t in self._failures.get(username, []) if now - t < self.lockout_seconds]
            window.append(now)
            self._failures[username] = window
            if len(window) >= self.max_attempts:
                self._locked_until[username] = now + self.lockout_seconds
                self._failures[username] = []

    def record_success(self, username: str) -> None:
        with self._lock:
            self._failures.pop(username, None)
            self._locked_until.pop(username, None)


login_throttle = LoginThrottle(
    max_attempts=settings.security.login_max_failed_attempts,
    lockout_seconds=settings.security.login_lockout_minutes * 60,
)

_revoked_token_ids: Dict[str, float] = {}
_revocation_lock = threading.Lock()


def revoke_token(jti: str, expires_at: float) -> None:
    with _revocation_lock:
        now = time.time()
        for key in [k for k, exp in _revoked_token_ids.items() if exp < now]:
            del _revoked_token_ids[key]
        _revoked_token_ids[jti] = expires_at


def is_token_revoked(jti: Optional[str]) -> bool:
    with _revocation_lock:
        return bool(jti) and jti in _revoked_token_ids


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

def create_access_token(
    user_id: str,
    role: str = ROLE_OPERATOR,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Generates signed JWT access token."""
    if role not in ALL_ROLES:
        raise ValueError(f"Unknown role '{role}'")
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.security.access_token_expire_minutes))
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire,
        "iat": now,
        "iss": TOKEN_ISSUER,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(
        payload,
        settings.security.jwt_secret_key,
        algorithm=settings.security.jwt_algorithm
    )


def verify_token(token: str) -> Dict[str, Any]:
    """Decodes and cryptographically verifies JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.security.jwt_secret_key,
            algorithms=[settings.security.jwt_algorithm],
            issuer=TOKEN_ISSUER,
            options={"require": ["exp", "iat", "sub", "role", "iss"]},
        )
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Access token has expired")
    except jwt.PyJWTError:
        raise AuthenticationError("Invalid access token signature or format")

    if payload.get("role") not in ALL_ROLES:
        raise AuthenticationError("Access token carries an unknown role")
    if is_token_revoked(payload.get("jti")):
        raise AuthenticationError("Access token has been revoked")
    return payload


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> Dict[str, Any]:
    """FastAPI dependency extracting the authenticated user from the bearer token."""
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Authentication required: send 'Authorization: Bearer <token>'")

    payload = verify_token(credentials.credentials)
    return {
        "user_id": payload["sub"],
        "role": payload["role"],
        "jti": payload.get("jti"),
        "exp": payload.get("exp"),
        "is_authenticated": True,
    }


def require_roles(allowed_roles: List[str]):
    """Enforces role-based access control on sensitive endpoints."""
    async def role_checker(user: Dict[str, Any] = Depends(get_current_user)):
        if user.get("role") not in allowed_roles:
            raise AuthorizationError(
                f"Role '{user.get('role')}' is not authorized. Requires: {', '.join(allowed_roles)}"
            )
        return user
    return role_checker
