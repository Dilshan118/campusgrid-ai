"""
Central Orchestrator: LangGraph State Machine
Routes tasks between Agent 1, Agent 2, Agent 3, and Agent 4 using typed state.
Uses the pluggable LLM Manager for query decomposition without hardcoded model references.
"""

from typing import Dict, Any, List
from backend.core.llm_manager import get_llm

llm = get_llm()

class CampusGridOrchestrator:
    """
    Coordinates multi-agent execution pipeline:
    Query -> NLP Extraction -> Forecast (Agent 1) -> Feasibility (Agent 2)
    -> Constraints (Agent 3) -> Dispatch & Explanation (Agent 4)
    """
    def __init__(self):
        self.active_model = llm.get_active_model_info()

    def route_query(self, user_prompt: str) -> Dict[str, Any]:
        """Plans which agents to call and handles task sequencing."""
        pass
