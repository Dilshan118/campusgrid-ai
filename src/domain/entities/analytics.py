"""
CampusGrid AI: Web Analytics Domain Entities
Interaction events behind the four analytics modules: query intent clustering, the
decision acceptance funnel, the XAI explanation A/B test, and citation click-through (MRR).
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

# Logged by the server itself (cannot be forged from the browser).
EVENT_QUERY_SUBMITTED = "query_submitted"
EVENT_SEARCH_PERFORMED = "search_performed"
EVENT_DECISION_APPROVED = "decision_approved"
EVENT_DECISION_REJECTED = "decision_rejected"

# Logged by the dashboard through POST /api/analytics/event.
EVENT_RECOMMENDATION_SHOWN = "recommendation_shown"
EVENT_EXPLANATION_OPENED = "explanation_opened"
EVENT_CITATION_CLICKED = "citation_clicked"
EVENT_SEARCH_RESULT_CLICKED = "search_result_clicked"

SERVER_EVENT_TYPES = {
    EVENT_QUERY_SUBMITTED,
    EVENT_SEARCH_PERFORMED,
    EVENT_DECISION_APPROVED,
    EVENT_DECISION_REJECTED,
}
CLIENT_EVENT_TYPES = {
    EVENT_RECOMMENDATION_SHOWN,
    EVENT_EXPLANATION_OPENED,
    EVENT_CITATION_CLICKED,
    EVENT_SEARCH_RESULT_CLICKED,
}

# XAI explanation presentation variants under test.
AB_VARIANT_CONCISE = "A_concise_summary"
AB_VARIANT_CITED = "B_cited_explanation"


class AnalyticsEvent(BaseModel):
    """A single dashboard or pipeline interaction."""
    event_id: Optional[int] = None
    event_type: str
    user_id: str
    role: Optional[str] = None
    session_id: Optional[str] = None
    audit_log_id: Optional[int] = None
    ab_variant: Optional[str] = None
    intent: Optional[str] = None
    query_text: Optional[str] = Field(default=None, max_length=500)
    rank: Optional[int] = Field(default=None, ge=1, le=100)
    clause_reference: Optional[str] = Field(default=None, max_length=200)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
