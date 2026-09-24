"""
CampusGrid AI: Policy & Standards RAG Router (Agent 3)
Searches Ceylon Electricity Board / PUCSL tariffs and ASHRAE-55 comfort standards.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends
from src.schemas.requests import RAGSearchRequest, RAGIngestRequest
from src.schemas.responses import APIResponse
from src.application.container import Container
from src.api.dependencies.container import get_app_container
from src.api.middleware.auth import require_roles, ALL_ROLES, ROLES_KNOWLEDGE_ADMINS
from src.api.routes.common import agent_response
from src.domain.entities.analytics import AnalyticsEvent, EVENT_SEARCH_PERFORMED
from src.domain.entities.audit import RECORD_KNOWLEDGE_INGESTION

router = APIRouter(prefix="/api/rag", tags=["Policy & RAG"])

@router.post("/search", response_model=APIResponse)
def search_regulatory_clauses(
    request: RAGSearchRequest,
    user: Dict[str, Any] = Depends(require_roles(ALL_ROLES)),
    container: Container = Depends(get_app_container)
):
    res = container.agent3_rag.execute({
        "query": request.query,
        "top_k": request.top_k
    })
    response = agent_response(res)
    container.analytics_service.track(AnalyticsEvent(
        event_type=EVENT_SEARCH_PERFORMED,
        user_id=user["user_id"],
        role=user["role"],
        session_id=request.session_id,
        intent="knowledge_search",
        query_text=request.query[:500],
        metadata={"results": len(response.data.get("citations", []))},
    ))
    return response

@router.get("/documents", response_model=APIResponse)
def list_indexed_documents(
    _user=Depends(require_roles(ALL_ROLES)),
    container: Container = Depends(get_app_container)
):
    return APIResponse(success=True, data=container.retrieval_service.index_stats())

@router.post("/ingest", response_model=APIResponse)
def ingest_regulatory_document(
    request: RAGIngestRequest,
    user: Dict[str, Any] = Depends(require_roles(ROLES_KNOWLEDGE_ADMINS)),
    container: Container = Depends(get_app_container)
):
    """Ingests a new policy document or re-indexes the default corpus directory.

    Restricted to facility managers: whatever is indexed here can change the tariff the solver uses.
    Clauses with instruction-like text or implausible figures are quarantined, never indexed.
    """
    retrieval_service = container.retrieval_service
    if request.text:
        result = retrieval_service.ingest_raw_document(
            text=request.text,
            source_document=request.source_document or "Custom Regulation",
            effective_date=request.effective_date or "2024-01-01"
        )
    else:
        result = retrieval_service.ingest_corpus_directory()

    container.audit_service.log_operator_action(
        user_id=user["user_id"],
        query=f"Knowledge base ingestion: {request.source_document if request.text else 'corpus directory re-index'}",
        agent_sequence={},
        decision={k: v for k, v in result.items() if k != "files_processed"},
        record_type=RECORD_KNOWLEDGE_INGESTION,
    )

    success = result.get("status") in ("success", "completed", "duplicate")
    return APIResponse(
        success=success,
        data=result,
        error=None if success else (result.get("message") or "No clauses were indexed.")
    )
