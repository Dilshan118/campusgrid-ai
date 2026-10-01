"""
CampusGrid AI: Policy & Standards RAG Router (Agent 3)
Searches Ceylon Electricity Board / PUCSL tariffs and ASHRAE-55 comfort standards.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Query
from src.schemas.requests import RAGSearchRequest, RAGIngestRequest, RegulationSubmissionRequest, RegulationReviewRequest
from src.schemas.responses import APIResponse
from src.application.container import Container
from src.api.dependencies.container import get_app_container
from src.api.middleware.auth import (
    require_roles, ROLES_REGULATION_READERS, ROLES_KNOWLEDGE_ADMINS, ROLES_REGULATION_REVIEWERS,
)
from src.domain.exceptions.base import WorkflowConflictError
from src.pipelines.document_ingestion.source_registry import list_sources
from src.api.routes.common import agent_response
from src.domain.entities.analytics import AnalyticsEvent, EVENT_SEARCH_PERFORMED
from src.domain.entities.audit import RECORD_KNOWLEDGE_INGESTION

router = APIRouter(prefix="/api/rag", tags=["Policy & RAG"])

@router.post("/search", response_model=APIResponse)
def search_regulatory_clauses(
    request: RAGSearchRequest,
    user: Dict[str, Any] = Depends(require_roles(ROLES_REGULATION_READERS)),
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
    _user=Depends(require_roles(ROLES_REGULATION_READERS)),
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
    if request.text and container.settings.regulation_review_required:
        raise WorkflowConflictError(
            "New regulation text must be reviewed by a second person before it is indexed. "
            "Submit it with POST /api/rag/submissions.",
            details={"status": 409, "error": "REVIEW_REQUIRED"},
        )
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


# ---------------------------------------------------------------------------
# Regulation lifecycle: trusted sources -> quarantined submission -> second-person review
# ---------------------------------------------------------------------------

@router.get("/sources", response_model=APIResponse)
def list_trusted_sources(_user=Depends(require_roles(ROLES_REGULATION_READERS))):
    """Publishers a regulation may come from, with the web domains their links must use."""
    return APIResponse(success=True, data=list_sources())

@router.post("/submissions", response_model=APIResponse)
def submit_regulation(
    request: RegulationSubmissionRequest,
    user: Dict[str, Any] = Depends(require_roles(ROLES_KNOWLEDGE_ADMINS)),
    container: Container = Depends(get_app_container)
):
    """Screen and quarantine a regulation document. Nothing is indexed until a second person approves it."""
    return APIResponse(success=True, data=container.regulation_review_service.submit(
        user_id=user["user_id"],
        text="\n".join(request.text_lines),
        title=request.title,
        publisher=request.publisher,
        reference=request.reference,
        effective_date=request.effective_date,
        source_url=request.source_url,
        supersedes=request.supersedes,
        filename=request.filename,
    ))

@router.get("/submissions", response_model=APIResponse)
def list_regulation_submissions(
    status: Optional[str] = Query(default=None, pattern=r"^(pending|approved|rejected)$"),
    _user=Depends(require_roles(ROLES_REGULATION_READERS)),
    container: Container = Depends(get_app_container)
):
    return APIResponse(success=True, data=container.regulation_review_service.list(status=status))

@router.get("/submissions/{submission_id}", response_model=APIResponse)
def get_regulation_submission(
    submission_id: int,
    _user=Depends(require_roles(ROLES_REGULATION_READERS)),
    container: Container = Depends(get_app_container)
):
    return APIResponse(success=True, data=container.regulation_review_service.get(submission_id, include_text=True))

@router.post("/submissions/{submission_id}/review", response_model=APIResponse)
def review_regulation_submission(
    submission_id: int,
    request: RegulationReviewRequest,
    user: Dict[str, Any] = Depends(require_roles(ROLES_REGULATION_REVIEWERS)),
    container: Container = Depends(get_app_container)
):
    """Approve (index it) or reject a quarantined document. The submitter cannot review their own."""
    return APIResponse(success=True, data=container.regulation_review_service.review(
        submission_id, reviewer_id=user["user_id"], approved=request.approved, notes=request.notes,
    ))
