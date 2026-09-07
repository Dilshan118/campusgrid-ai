"""
CampusGrid AI: Policy & Standards RAG Router (Agent 3)
Searches Ceylon Electricity Board / PUCSL tariffs and ASHRAE-55 comfort standards.
"""

from fastapi import APIRouter, Depends
from src.schemas.requests import RAGSearchRequest
from src.schemas.responses import APIResponse
from src.application.container import Container
from src.api.dependencies.container import get_app_container

router = APIRouter(prefix="/api/rag", tags=["Policy & RAG"])

@router.post("/search", response_model=APIResponse)
async def search_regulatory_clauses(
    request: RAGSearchRequest,
    container: Container = Depends(get_app_container)
):
    res = container.agent3_rag.execute({
        "query": request.query,
        "top_k": request.top_k
    })
    return APIResponse(
        success=res.success,
        data=res.data,
        error=res.error,
        execution_time_ms=res.execution_time_ms
    )
