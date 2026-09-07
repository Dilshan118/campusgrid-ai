"""
Backwards compatibility shim for AuditLogStore.
Delegates to src.application.services.audit_service.
"""

from typing import Dict, Any
from src.application.container import get_container

class AuditLogStore:
    def __init__(self):
        self.container = get_container()
        self.audit_service = self.container.audit_service

    def log_transaction(
        self,
        user_id: str,
        query_text: str,
        agent_sequence: Dict[str, Any],
        final_decision: Dict[str, Any],
        human_approved: bool = False
    ):
        return self.audit_service.log_operator_action(
            user_id=user_id,
            query=query_text,
            agent_sequence=agent_sequence,
            decision=final_decision,
            approved=human_approved
        )

__all__ = ["AuditLogStore"]
