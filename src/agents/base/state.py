"""
CampusGrid AI: Base Agent State & Message Contracts
Typed structures for agent inputs, outputs, and inter-agent coordination.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class AgentExecutionResult(BaseModel):
    """Standardized output produced by every specialized agent."""
    agent_name: str
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    citations: List[Dict[str, Any]] = Field(default_factory=list)
