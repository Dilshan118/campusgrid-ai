"""
CampusGrid AI: Health Check Router
Reports system status, software version, and active infrastructure providers.
"""

from fastapi import APIRouter, Depends
from src.schemas.responses import HealthResponse
from src.application.container import Container
from src.api.dependencies.container import get_app_container

router = APIRouter(prefix="/api/health", tags=["Health"])

@router.get("", response_model=HealthResponse)
def health_check(container: Container = Depends(get_app_container)):
    return HealthResponse(
        status="online",
        system=container.settings.app_name,
        version=container.settings.app_version,
        active_providers={
            "llm_provider": type(container.llm_provider).__name__,
            "embedding_provider": type(container.embedding_provider).__name__,
            "vector_store": type(container.vector_store).__name__,
            "cache_provider": type(container.cache_provider).__name__,
            "database_provider": container.settings.database.provider,
            "reranker": type(container.reranker).__name__,
        },
        agent_slices=container.slice_status(),
        dense_search_enabled=container.retrieval_service.dense_enabled,
    )
