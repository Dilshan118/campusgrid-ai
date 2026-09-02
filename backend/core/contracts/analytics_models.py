"""
CampusGrid AI: Web Analytics Contract Models
Defines schemas for query logging, intent clusters, and conversion funnels.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

class QueryLogEntry(BaseModel):
    query_text: str
    session_id: str
    intent_cluster: Optional[str] = None
    timestamp: str

class FunnelEventEntry(BaseModel):
    session_id: str
    step_name: str = Field(..., description="1_shown, 2_explanation_opened, 3_citation_clicked, 4_approved")
    action_taken: str = Field(..., description="approve, modify, reject")
    timestamp: str

class ABExperimentResult(BaseModel):
    variant_a_impressions: int
    variant_a_conversions: int
    variant_a_rate: float
    variant_b_impressions: int
    variant_b_conversions: int
    variant_b_rate: float
    winning_variant: str
