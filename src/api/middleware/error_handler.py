"""
CampusGrid AI: Global Error Handling Middleware & Exception Handlers
Maps domain exceptions to HTTP responses cleanly.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from src.domain.exceptions.base import (
    DomainException,
    InfeasibleOptimizationError,
    SafetyViolationError,
    EntityNotFoundError,
    ProviderException,
)

async def domain_exception_handler(request: Request, exc: DomainException):
    status_code = 400
    if isinstance(exc, EntityNotFoundError):
        status_code = 404
    elif isinstance(exc, InfeasibleOptimizationError):
        status_code = 422
    elif isinstance(exc, SafetyViolationError):
        status_code = 422
    elif isinstance(exc, ProviderException):
        status_code = 502

    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details
        }
    )

async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected system error occurred.",
            "details": {"exception_type": type(exc).__name__, "message": str(exc)}
        }
    )
