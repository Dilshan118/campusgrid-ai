"""
Backwards compatibility shim for CampusGridOrchestrator.
Delegates to src.agents.coordinator.agent.CampusGridOrchestrator.
"""

from typing import Dict, Any
from src.application.container import get_container

class CampusGridOrchestrator:
    def __init__(self):
        self.container = get_container()
        self._orchestrator = self.container.orchestrator

    def route_query(self, user_prompt: str) -> Dict[str, Any]:
        res = self._orchestrator.execute({"query": user_prompt})
        return res.data if res.success else {"error": res.error}

__all__ = ["CampusGridOrchestrator"]
