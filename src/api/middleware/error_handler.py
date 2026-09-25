"""
CampusGrid AI: Global Error Handling Middleware & Exception Handlers
Maps domain exceptions to HTTP responses cleanly.
"""

import logging
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse
from src.domain.exceptions.base import (
    DomainException,
    InfeasibleOptimizationError,
    SafetyViolationError,
    EntityNotFoundError,
    ProviderException,
)

logger = logging.getLogger("campusgrid.api")

# Security exceptions carry their intended HTTP status in details["status"]
# (401 unauthenticated, 403 forbidden, 429 locked out, 413 too large, ...).
_ALLOWED_DETAIL_STATUSES = {400, 401, 403, 404, 409, 413, 422, 429, 500, 502, 503}


def _status_for(exc: DomainException) -> int:
    declared = (exc.details or {}).get("status")
    if isinstance(declared, int) and declared in _ALLOWED_DETAIL_STATUSES:
        return declared
    if isinstance(exc, EntityNotFoundError):
        return 404
    if isinstance(exc, (InfeasibleOptimizationError, SafetyViolationError)):
        return 422
    if isinstance(exc, ProviderException):
        return 502
    return 400


async def domain_exception_handler(request: Request, exc: DomainException):
    status_code = _status_for(exc)
    headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
    details = {k: v for k, v in (exc.details or {}).items() if k != "status"}
    message = exc.message

    if isinstance(exc, ProviderException):
        # Provider messages and details embed raw driver / SDK text (hosts, SQL, key fragments).
        logger.warning(
            "Provider failure on %s %s (request_id=%s): %s | %s",
            request.method, request.url.path, request.headers.get("X-Request-ID"), exc.message, details,
        )
        provider = details.get("provider", "external")
        message = f"The {provider} provider call failed; details are in the server log."
        details = {"provider": provider}

    return JSONResponse(
        status_code=status_code,
        headers=headers,
        content={
            "success": False,
            "error_code": exc.error_code,
            "message": message,
            "details": details
        }
    )


async def generic_exception_handler(request: Request, exc: Exception):
    # The exception text can contain file paths, SQL or provider responses, so it is
    # logged server-side with the request ID and never returned to the client.
    logger.exception(
        "Unhandled error on %s %s (request_id=%s)",
        request.method, request.url.path, request.headers.get("X-Request-ID"),
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected system error occurred.",
            "details": {"exception_type": type(exc).__name__}
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # FastAPI's default body echoes the submitted input; only field locations and messages are returned here.
    errors = [
        {"field": ".".join(str(part) for part in err.get("loc", ()) if part != "body"), "message": err.get("msg")}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error_code": "VALIDATION_ERROR",
            "message": "The request is missing a field or contains an invalid value.",
            "details": {"errors": errors},
        },
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        headers=getattr(exc, "headers", None),
        content={
            "success": False,
            "error_code": "NOT_FOUND" if exc.status_code == 404 else f"HTTP_{exc.status_code}",
            "message": str(exc.detail),
            "details": {},
        },
    )
