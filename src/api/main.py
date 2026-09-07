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
from src.api.middleware.error_handler import domain_exception_handler, generic_exception_handler
from src.api.routes import (
    health_router,
    orchestrator_router,
    telemetry_router,
    simulation_router,
    optimizer_router,
    rag_router,
    analytics_router,
    audit_router,
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
app.add_exception_handler(DomainException, domain_exception_handler)

# 2. Middlewares (Order: Tracing -> CORS)
app.add_middleware(RequestTracingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Mount Domain Routers
app.include_router(health_router)
app.include_router(orchestrator_router)
app.include_router(telemetry_router)
app.include_router(simulation_router)
app.include_router(optimizer_router)
app.include_router(rag_router)
app.include_router(analytics_router)
app.include_router(audit_router)
