"""
CampusGrid AI: FastAPI Application Entry Point
High-performance asynchronous REST backend and multi-agent coordination gateway.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from src.config.settings import get_settings
from src.application.container import get_container
from src.domain.exceptions.base import DomainException
from src.api.middleware.request_tracing import RequestTracingMiddleware
from src.api.middleware.sanitization import InputSanitizationMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from src.api.middleware.error_handler import (
    domain_exception_handler,
    generic_exception_handler,
    validation_exception_handler,
    http_exception_handler,
)
from src.api.routes import (
    health_router,
    orchestrator_router,
    telemetry_router,
    simulation_router,
    optimizer_router,
    rag_router,
    analytics_router,
    audit_router,
    auth_router,
)

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize container and database/storage on startup
    container = get_container()
    if container.session_manager:
        container.session_manager.init_database()
    yield

app = FastAPI(
    title=settings.app_name,
    description="Autonomous Multi-Agent Microgrid Energy Management System & Cyber-Physical Digital Twin",
    version=settings.app_version,
    lifespan=lifespan
)

# 1. Custom Exception Handlers
# The generic handler must be registered too, otherwise any non-domain exception
# escapes as an unformatted 500 with a stack trace in the response body.
app.add_exception_handler(DomainException, domain_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# 2. Middlewares (Order: Sanitization -> Tracing -> CORS)
app.add_middleware(InputSanitizationMiddleware, max_body_bytes=settings.security.max_request_body_bytes)
app.add_middleware(RequestTracingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Trace-ID"],
    expose_headers=["X-Request-ID", "X-Trace-ID", "X-Process-Time-Ms", "X-Privacy-Mechanism"],
)

# 3. Mount Domain Routers
app.include_router(auth_router)
app.include_router(health_router)
app.include_router(orchestrator_router)
app.include_router(telemetry_router)
app.include_router(simulation_router)
app.include_router(optimizer_router)
app.include_router(rag_router)
app.include_router(analytics_router)
app.include_router(audit_router)

