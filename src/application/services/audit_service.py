"""
CampusGrid AI: Audit Service
Handles transaction recording, retrieval of audit trails, human approval decisions,
and verification of the tamper-evident hash chain.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from src.domain.interfaces.repositories import AuditLogRepository
from src.domain.entities.audit import (
    AuditRecord,
    RECORD_DISPATCH_RECOMMENDATION,
    RECORD_APPROVAL_DECISION,
    APPROVAL_PENDING,
    APPROVAL_APPROVED,
    APPROVAL_REJECTED,
    APPROVAL_NOT_REQUIRED,
    compute_audit_signature,
)
from src.domain.exceptions.base import DomainException, EntityNotFoundError, WorkflowConflictError

# A day-ahead plan is only meaningful for the day it was computed for.
RECOMMENDATION_VALIDITY_HOURS = 24


class AuditService:
    """Provides application-level audit logging, approval workflow and verification."""

    def __init__(self, audit_repo: AuditLogRepository):
        self.audit_repo = audit_repo

    def log_operator_action(
        self,
        user_id: str,
        query: str,
        agent_sequence: Dict[str, Any],
        decision: Dict[str, Any],
        approved: bool = False,
        record_type: str = RECORD_DISPATCH_RECOMMENDATION,
        approval_status: str = APPROVAL_NOT_REQUIRED,
    ) -> int:
        record = AuditRecord(
            user_id=user_id,
            query_text=query,
            agent_sequence=agent_sequence,
            final_decision=decision,
            human_approved=approved,
            record_type=record_type,
            approval_status=approval_status,
        )
        return self.audit_repo.log_transaction(record)

    def get_audit_trail(self, limit: int = 50) -> List[AuditRecord]:
        return self.audit_repo.list_recent(limit=limit)

    # ------------------------------------------------------------------
    # Read views (what the dashboard renders)
    # ------------------------------------------------------------------

    def _effective_status(self, record: AuditRecord, decision: Optional[AuditRecord]) -> str:
        """A recommendation's live status comes from its decision row, never from editing it."""
        if record.record_type != RECORD_DISPATCH_RECOMMENDATION or record.approval_status != APPROVAL_PENDING:
            return record.approval_status
        if decision is not None:
            return decision.approval_status
        return "expired" if self._is_expired(record) else APPROVAL_PENDING

    def to_view(self, record: AuditRecord, include_agent_sequence: bool = True) -> Dict[str, Any]:
        view = record.model_dump()
        if not include_agent_sequence:
            view.pop("agent_sequence", None)
        decision = None
        if record.record_type == RECORD_DISPATCH_RECOMMENDATION:
            decision = self.audit_repo.get_decision_for(record.log_id)
        view["effective_status"] = self._effective_status(record, decision)
        if record.record_type == RECORD_DISPATCH_RECOMMENDATION:
            view["decision"] = None if decision is None else {
                "decision_log_id": decision.log_id,
                "decided_by": decision.user_id,
                "decided_at": decision.timestamp,
                "status": decision.approval_status,
                "notes": decision.final_decision.get("notes"),
            }
        return view

    def list_views(
        self,
        limit: int = 20,
        record_type: Optional[str] = None,
        status: Optional[str] = None,
        include_agent_sequence: bool = False,
    ) -> List[Dict[str, Any]]:
        # Over-fetch so filtering still fills the page on a mixed trail.
        records = self.audit_repo.list_recent(limit=limit * 5 if (record_type or status) else limit)
        views = []
        for r in records:
            if record_type and r.record_type != record_type:
                continue
            view = self.to_view(r, include_agent_sequence=include_agent_sequence)
            if status and view["effective_status"] != status:
                continue
            views.append(view)
            if len(views) >= limit:
                break
        return views

    def get_record_view(self, log_id: int) -> Dict[str, Any]:
        record = self.audit_repo.get_by_id(log_id)
        if record is None:
            raise EntityNotFoundError(entity_type="AuditRecord", identifier=log_id)
        return self.to_view(record, include_agent_sequence=True)

    def list_pending(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.list_views(limit=limit, record_type=RECORD_DISPATCH_RECOMMENDATION, status=APPROVAL_PENDING)

    # ------------------------------------------------------------------
    # Human-in-the-loop decision
    # ------------------------------------------------------------------

    def record_decision(
        self,
        log_id: int,
        approver_id: str,
        approved: bool,
        notes: Optional[str] = None,
        acknowledge_warnings: bool = False,
    ) -> Dict[str, Any]:
        record = self.audit_repo.get_by_id(log_id)
        if record is None:
            raise EntityNotFoundError(entity_type="AuditRecord", identifier=log_id)
        if record.record_type != RECORD_DISPATCH_RECOMMENDATION or record.approval_status != APPROVAL_PENDING:
            raise WorkflowConflictError(
                f"Audit record #{log_id} is a '{record.record_type}' entry and does not require approval.",
                details={"log_id": log_id, "record_type": record.record_type},
            )

        existing = self.audit_repo.get_decision_for(log_id)
        if existing is not None:
            raise WorkflowConflictError(
                f"Recommendation #{log_id} was already {existing.approval_status} by "
                f"{existing.user_id} at {existing.timestamp}.",
                details={"log_id": log_id, "decision_log_id": existing.log_id, "status": 409},
            )
        if self._is_expired(record):
            raise WorkflowConflictError(
                f"Recommendation #{log_id} is older than {RECOMMENDATION_VALIDITY_HOURS} hours; "
                "re-run the plan with current data before deciding.",
                details={"log_id": log_id, "created_at": record.timestamp},
            )

        notes = (notes or "").strip() or None
        if not approved and not notes:
            raise DomainException(
                message="A rejection must include a reason in operator_notes.",
                error_code="VALIDATION_ERROR",
                details={"status": 422, "field": "operator_notes"},
            )

        warnings = list(record.final_decision.get("warnings") or [])
        if approved and warnings and not acknowledge_warnings:
            raise WorkflowConflictError(
                "This recommendation carries safety or verification warnings. "
                "Review them and resend with acknowledge_warnings=true to approve.",
                details={"log_id": log_id, "warnings": warnings},
            )

        decision_status = APPROVAL_APPROVED if approved else APPROVAL_REJECTED
        decision = AuditRecord(
            user_id=approver_id,
            query_text=f"Decision on recommendation #{log_id}",
            agent_sequence={},
            final_decision={
                "decision": decision_status,
                "recommendation_log_id": log_id,
                "notes": notes,
                "acknowledged_warnings": warnings if approved else [],
                "net_savings_lkr": record.final_decision.get("net_savings_lkr"),
                "requested_by": record.user_id,
            },
            human_approved=approved,
            record_type=RECORD_APPROVAL_DECISION,
            approval_status=decision_status,
            parent_log_id=log_id,
        )
        decision_id = self.audit_repo.log_transaction(decision)
        return {
            "recommendation_log_id": log_id,
            "decision_log_id": decision_id,
            "status": decision_status,
            "decided_by": approver_id,
            "decided_at": decision.timestamp,
            "notes": notes,
        }

    # ------------------------------------------------------------------
    # Tamper evidence
    # ------------------------------------------------------------------

    def verify_chain(self) -> Dict[str, Any]:
        """Recomputes every signature in order; any edited, inserted or deleted row breaks the chain."""
        previous: Optional[str] = None
        records = self.audit_repo.list_all_ascending()
        # Rows written before signing was introduced (an upgraded database) carry no signature.
        # They are reported, not treated as tampering; the chain starts at the first signed row.
        legacy = 0
        while legacy < len(records) and records[legacy].signature is None:
            legacy += 1

        for r in records[legacy:]:
            expected = compute_audit_signature(r, previous)
            if r.previous_signature != previous or r.signature != expected:
                return {
                    "valid": False,
                    "records_checked": len(records) - legacy,
                    "unsigned_legacy_records": legacy,
                    "first_invalid_log_id": r.log_id,
                }
            previous = r.signature
        return {
            "valid": True,
            "records_checked": len(records) - legacy,
            "unsigned_legacy_records": legacy,
            "first_invalid_log_id": None,
        }

    @staticmethod
    def _is_expired(record: AuditRecord) -> bool:
        try:
            created = datetime.fromisoformat(record.timestamp)
        except (TypeError, ValueError):
            return False
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - created > timedelta(hours=RECOMMENDATION_VALIDITY_HOURS)
