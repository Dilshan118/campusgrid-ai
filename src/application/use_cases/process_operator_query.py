"""
CampusGrid AI: Process Operator Query Use Case
Coordinates the multi-agent pipeline from query parsing to grounded recommendation synthesis.
"""

from typing import Dict, Any
from src.agents.coordinator.agent import CampusGridOrchestrator

class ProcessOperatorQueryUseCase:
    """Coordinates end-to-end multi-agent execution for an operator query."""

    def __init__(self, orchestrator: CampusGridOrchestrator):
        self.orchestrator = orchestrator

    def execute(self, query: str, user_id: str = "operator_facility_manager", **kwargs) -> Dict[str, Any]:
        payload = {"query": query, "user_id": user_id, **kwargs}
        res = self.orchestrator.execute(payload)
        if not res.success:
            return {
                "success": False,
                "error": res.error,
                "execution_time_ms": res.execution_time_ms
            }
        return {
            "success": True,
            "data": res.data,
            "execution_time_ms": res.execution_time_ms
        }
