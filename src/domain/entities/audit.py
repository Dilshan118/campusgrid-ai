"""
CampusGrid AI: Audit Domain Entities
Immutable representations of query transactions, intermediate agent outputs, decisions, and approvals.

The audit store is append-only. A recommendation row is never edited when a manager
approves it; instead a separate `approval_decision` row is appended that points back to
it through `parent_log_id`. Every row is chained to the previous one with a SHA-256
signature, so any later edit or deletion is detectable (see compute_audit_signature).
With a signing key configured the signature is an HMAC, so someone who can write to the
database but does not hold the key cannot recompute a valid chain after editing it.
"""

import hashlib
import hmac
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

# What kind of transaction the row records.
RECORD_DISPATCH_RECOMMENDATION = "dispatch_recommendation"
RECORD_POLICY_LOOKUP = "policy_lookup"
RECORD_WHAT_IF_SIMULATION = "what_if_simulation"
RECORD_FORECAST_REVIEW = "forecast_review"
RECORD_OUT_OF_SCOPE = "out_of_scope_query"
RECORD_KNOWLEDGE_INGESTION = "knowledge_ingestion"
RECORD_APPROVAL_DECISION = "approval_decision"

# Where the row stands in the human approval workflow.
APPROVAL_PENDING = "pending"
APPROVAL_APPROVED = "approved"
APPROVAL_REJECTED = "rejected"
APPROVAL_NOT_REQUIRED = "not_required"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def canonical_timestamp(value: str) -> str:
    """Normalizes ISO / PostgreSQL timestamp strings so a stored row hashes identically on read-back."""
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return str(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


class AuditRecord(BaseModel):
    """Immutable audit trail entry for non-repudiation and compliance."""
    log_id: Optional[int] = None
    timestamp: str = Field(default_factory=_utc_now_iso)
    user_id: str
    query_text: str
    agent_sequence: Dict[str, Any]
    final_decision: Dict[str, Any]
    human_approved: bool = False
    record_type: str = RECORD_DISPATCH_RECOMMENDATION
    approval_status: str = APPROVAL_NOT_REQUIRED
    parent_log_id: Optional[int] = None
    previous_signature: Optional[str] = None
    signature: Optional[str] = None


def compute_audit_signature(
    record: AuditRecord, previous_signature: Optional[str], signing_key: Optional[bytes] = None
) -> str:
    """SHA-256 over the previous row's signature plus this row's canonical content (log_id excluded,
    because a database assigns it only after the insert). HMAC-SHA256 when `signing_key` is given
    (SEC-09); both are 64 hex characters, so the schema is unchanged."""
    payload = {
        "timestamp": canonical_timestamp(record.timestamp),
        "user_id": record.user_id,
        "query_text": record.query_text,
        "agent_sequence": record.agent_sequence,
        "final_decision": record.final_decision,
        "human_approved": record.human_approved,
        "record_type": record.record_type,
        "approval_status": record.approval_status,
        "parent_log_id": record.parent_log_id,
        "previous_signature": previous_signature or "",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    if signing_key:
        return hmac.new(signing_key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
