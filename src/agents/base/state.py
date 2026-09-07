"""
CampusGrid AI: Base Agent State & Message Contracts
Typed structures for agent inputs, outputs, and inter-agent coordination.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class AgentMessage(BaseModel):
    """Message exchanged between agents or from the coordinator."""
    sender: str
    recipient: str
    content: str
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class AgentExecutionResult(BaseModel):
    """Standardized output produced by every specialized agent."""
    agent_name: str
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    citations: List[Dict[str, Any]] = Field(default_factory=list)

class MultiAgentState(BaseModel):
    """Shared state container for the LangGraph sequential coordination pipeline."""
    session_id: str
    user_query: str
    parsed_intent: Dict[str, Any] = Field(default_factory=dict)
    current_step: str = "init"
    telemetry_forecast: Optional[Dict[str, Any]] = None
    digital_twin_feasibility: Optional[Dict[str, Any]] = None
    regulatory_constraints: Optional[Dict[str, Any]] = None
    optimization_result: Optional[Dict[str, Any]] = None
    xai_explanation: Optional[str] = None
    faithfulness_score: Optional[float] = None
    is_approved_by_human: bool = False
    errors: List[str] = Field(default_factory=list)
