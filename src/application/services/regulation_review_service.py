"""
CampusGrid AI: Regulation Review Service (quarantine -> maker-checker approval -> index)
Whatever enters the regulation corpus can change the tariff the solver prices a plan with, so
a new document never becomes active on one person's say-so:

  1. Submit   a facility manager uploads the text with its publisher (from the trusted-source
              registry), a citable reference, its effective date and, if it replaces an older
              document, that document's title. It is screened exactly as ingestion would screen
              it, stored on the append-only audit trail with its SHA-256, and NOT indexed.
  2. Review   a different person with rag:review (another facility manager, or the energy
              auditor) reads the screening report and approves or rejects it.
  3. Activate on approval the stored text — checked against its SHA-256 — is indexed, and any
              superseded document stops being retrieved from the new one's effective date.

The audit trail is the store: submissions and reviews are replayed at startup, so approved
documents are re-indexed into an in-memory index and supersessions survive restarts.
"""

import hashlib
import logging
import threading
from typing import Any, Dict, List, Optional
from src.domain.entities.audit import (
    RECORD_KNOWLEDGE_SUBMISSION,
    RECORD_KNOWLEDGE_REVIEW,
    RECORD_KNOWLEDGE_INGESTION,
    APPROVAL_PENDING,
    APPROVAL_APPROVED,
    APPROVAL_REJECTED,
)
from src.domain.exceptions.base import DomainException, EntityNotFoundError, WorkflowConflictError
from src.pipelines.document_ingestion.source_registry import source_problems, TRUSTED_SOURCES
from src.application.services.audit_service import AuditService

logger = logging.getLogger("campusgrid.regulation_review")

_REPLAY_LIMIT = 1000


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class RegulationReviewService:
    def __init__(self, retrieval_service: Any, audit_service: AuditService):
        self.retrieval_service = retrieval_service
        self.audit_service = audit_service
        self.audit_repo = audit_service.audit_repo
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ submit

    def submit(
        self,
        user_id: str,
        text: str,
        title: str,
        publisher: str,
        reference: str,
        effective_date: str,
        source_url: Optional[str] = None,
        supersedes: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        title, reference = title.strip(), reference.strip()
        problems = source_problems(publisher, source_url)
        if supersedes and supersedes.strip().lower() == title.lower():
            problems.append("A document cannot supersede itself; give the new version its own title (e.g. with its year).")
        if problems:
            raise DomainException(" ".join(problems), "VALIDATION_ERROR", {"status": 422, "problems": problems})

        screening = self.retrieval_service.ingestion_pipeline.preview_raw_text(text, title, effective_date)
        if not screening["clauses_accepted"]:
            raise DomainException(
                "No clause in this document passed screening, so there is nothing to review.",
                "REGULATION_REJECTED_BY_SCREENING",
                {"status": 422, "screening": screening},
            )
        submission = {
            "title": title,
            "publisher": publisher.upper(),
            "publisher_name": TRUSTED_SOURCES[publisher.upper()]["name"],
            "reference": reference,
            "source_url": source_url,
            "effective_date": effective_date,
            "supersedes": (supersedes or "").strip() or None,
            "filename": filename,
            "sha256": _sha256(text),
            "text": text,
            "screening": screening,
        }
        log_id = self.audit_service.log_operator_action(
            user_id=user_id,
            query=f"Regulation submitted for review: {title} ({publisher.upper()} {reference})",
            agent_sequence={},
            decision=submission,
            record_type=RECORD_KNOWLEDGE_SUBMISSION,
            approval_status=APPROVAL_PENDING,
        )
        return self.get(log_id)

    # ------------------------------------------------------------------ read

    def _view(self, record, review) -> Dict[str, Any]:
        d = record.final_decision
        return {
            "submission_id": record.log_id,
            "submitted_by": record.user_id,
            "submitted_at": record.timestamp,
            **{k: d.get(k) for k in ("title", "publisher", "publisher_name", "reference", "source_url",
                                     "effective_date", "supersedes", "filename", "sha256", "screening")},
            "status": review.approval_status if review else APPROVAL_PENDING,
            "review": None if review is None else {
                "reviewed_by": review.user_id,
                "reviewed_at": review.timestamp,
                "notes": review.final_decision.get("notes"),
            },
        }

    def list(self, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        records = self.audit_repo.list_recent(limit=_REPLAY_LIMIT, record_type=RECORD_KNOWLEDGE_SUBMISSION)
        reviews = self.audit_repo.get_children_for([r.log_id for r in records], RECORD_KNOWLEDGE_REVIEW)
        views = [self._view(r, reviews.get(r.log_id)) for r in records]
        return [v for v in views if status is None or v["status"] == status][:limit]

    def get(self, submission_id: int, include_text: bool = False) -> Dict[str, Any]:
        record = self.audit_repo.get_by_id(submission_id)
        if record is None or record.record_type != RECORD_KNOWLEDGE_SUBMISSION:
            raise EntityNotFoundError(entity_type="RegulationSubmission", identifier=submission_id)
        review = self.audit_repo.get_children_for([submission_id], RECORD_KNOWLEDGE_REVIEW).get(submission_id)
        view = self._view(record, review)
        if include_text:
            view["text"] = record.final_decision.get("text")
        return view

    # ------------------------------------------------------------------ review

    def review(self, submission_id: int, reviewer_id: str, approved: bool, notes: Optional[str] = None) -> Dict[str, Any]:
        notes = (notes or "").strip() or None
        with self._lock:
            record = self.audit_repo.get_by_id(submission_id)
            if record is None or record.record_type != RECORD_KNOWLEDGE_SUBMISSION:
                raise EntityNotFoundError(entity_type="RegulationSubmission", identifier=submission_id)
            existing = self.audit_repo.get_children_for([submission_id], RECORD_KNOWLEDGE_REVIEW).get(submission_id)
            if existing is not None:
                raise WorkflowConflictError(
                    f"Submission #{submission_id} was already {existing.approval_status} by {existing.user_id}.",
                    details={"submission_id": submission_id, "status": 409},
                )
            if reviewer_id == record.user_id:
                raise WorkflowConflictError(
                    "The person who submitted a regulation cannot also approve it; a second reviewer must.",
                    details={"submission_id": submission_id, "status": 409},
                )
            if not approved and not notes:
                raise DomainException("A rejection must include a reason.", "VALIDATION_ERROR",
                                      {"status": 422, "field": "notes"})

            d = record.final_decision
            if approved and _sha256(d.get("text") or "") != d.get("sha256"):
                raise WorkflowConflictError(
                    f"Submission #{submission_id} no longer matches its recorded SHA-256; it will not be indexed.",
                    details={"submission_id": submission_id, "status": 409},
                )
            # The decision is recorded before indexing: if indexing then fails, the approved document is
            # re-applied by replay_approved() at the next start instead of being indexed with no review.
            self.audit_service.log_operator_action(
                user_id=reviewer_id,
                query=f"Review of regulation submission #{submission_id}",
                agent_sequence={},
                decision={"decision": APPROVAL_APPROVED if approved else APPROVAL_REJECTED, "notes": notes,
                          "submission_id": submission_id, "sha256": d.get("sha256")},
                record_type=RECORD_KNOWLEDGE_REVIEW,
                approval_status=APPROVAL_APPROVED if approved else APPROVAL_REJECTED,
                parent_log_id=submission_id,
            )
            ingestion = None
            if approved:
                ingestion = self._activate(d)
                self.audit_service.log_operator_action(
                    user_id=reviewer_id,
                    query=f"Knowledge base ingestion: {d['title']} (approved submission #{submission_id})",
                    agent_sequence={},
                    decision={**ingestion, "submission_id": submission_id, "submitted_by": record.user_id},
                    record_type=RECORD_KNOWLEDGE_INGESTION,
                )
        return {**self.get(submission_id), "ingestion": ingestion}

    def _activate(self, submission: Dict[str, Any]) -> Dict[str, Any]:
        result = self.retrieval_service.ingest_raw_document(
            text=submission["text"],
            source_document=submission["title"],
            effective_date=submission["effective_date"],
            force_source=True,
        )
        if submission.get("supersedes"):
            self.retrieval_service.register_supersession(submission["supersedes"], submission["effective_date"])
        return {k: v for k, v in result.items() if k in ("status", "clauses_added", "duplicates_skipped", "rejected_clauses")}

    # ------------------------------------------------------------------ startup

    def replay_approved(self) -> int:
        """Re-applies every approved submission (duplicates are skipped by the ingestion pipeline), so an
        in-memory index and the supersession list match the audit trail after a restart."""
        try:
            records = self.audit_repo.list_recent(limit=_REPLAY_LIMIT, record_type=RECORD_KNOWLEDGE_SUBMISSION)
            reviews = self.audit_repo.get_children_for([r.log_id for r in records], RECORD_KNOWLEDGE_REVIEW)
        except Exception as exc:  # database unreachable at startup: approved documents stay as stored
            logger.warning("Could not replay approved regulation submissions (%s).", type(exc).__name__)
            return 0
        applied = 0
        for record in reversed(records):  # oldest first, so later supersessions win
            review = reviews.get(record.log_id)
            if review is not None and review.approval_status == APPROVAL_APPROVED:
                self._activate(record.final_decision)
                applied += 1
        return applied
