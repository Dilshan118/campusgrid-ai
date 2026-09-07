"""
CampusGrid AI: Audit Service
Handles transaction recording, retrieval of audit trails, and human approval signing.
"""

from typing import List, Dict, Any, Optional
from src.domain.interfaces.repositories import AuditLogRepository
from src.domain.entities.audit import AuditRecord

class AuditService:
    """Provides application-level audit logging and verification."""

    def __init__(self, audit_repo: AuditLogRepository):
        self.audit_repo = audit_repo

    def log_operator_action(
        self,
        user_id: str,
        query: str,
        agent_sequence: Dict[str, Any],
        decision: Dict[str, Any],
        approved: bool = False
    ) -> int:
        record = AuditRecord(
            user_id=user_id,
            query_text=query,
            agent_sequence=agent_sequence,
            final_decision=decision,
            human_approved=approved
        )
        return self.audit_repo.log_transaction(record)

    def get_audit_trail(self, limit: int = 50) -> List[AuditRecord]:
        return self.audit_repo.list_recent(limit=limit)
