"""
CampusGrid AI: Public API Response Schemas
Pydantic DTOs for client responses.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    status: str
    system: str
    version: str
    active_providers: Dict[str, str]
    agent_slices: Dict[str, str] = Field(default_factory=dict)
    dense_search_enabled: bool = True

class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None
