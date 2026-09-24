from src.api.routes.health import router as health_router
from src.api.routes.orchestrator import router as orchestrator_router
from src.api.routes.telemetry import router as telemetry_router
from src.api.routes.simulation import router as simulation_router
from src.api.routes.optimizer import router as optimizer_router
from src.api.routes.rag import router as rag_router
from src.api.routes.analytics import router as analytics_router
from src.api.routes.audit import router as audit_router
from src.api.routes.auth import router as auth_router

__all__ = [
    "health_router",
    "orchestrator_router",
    "telemetry_router",
    "simulation_router",
    "optimizer_router",
    "rag_router",
    "analytics_router",
    "audit_router",
    "auth_router",
]

