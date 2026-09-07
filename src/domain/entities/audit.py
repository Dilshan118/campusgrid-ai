"""
CampusGrid AI: Audit Domain Entities
Immutable representations of query transactions, intermediate agent outputs, decisions, and approvals.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class AuditRecord(BaseModel):
    """Immutable audit trail entry for non-repudiation and compliance."""
    log_id: Optional[int] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    user_id: str
    query_text: str
    agent_sequence: Dict[str, Any]
    final_decision: Dict[str, Any]
    human_approved: bool = False
    signature: Optional[str] = None
