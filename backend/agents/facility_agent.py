"""
Backwards compatibility shim for FacilityInterfaceAgent.
Delegates to the modular Multi-Agent Container and CampusGridOrchestrator.
"""

from typing import Dict, Any
from src.application.container import get_container

class FacilityInterfaceAgent:
    def __init__(self, model_name: str = "gemini-1.5-flash"):
        self.container = get_container()
        self.orchestrator = self.container.orchestrator

    def process_query(self, user_message: str, current_telemetry: Dict[str, Any] = None) -> Dict[str, Any]:
        res = self.orchestrator.execute({"query": user_message})
        return res.data if res.success else {"error": res.error}

__all__ = ["FacilityInterfaceAgent"]
