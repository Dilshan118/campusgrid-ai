"""
CampusGrid AI: Retrieve Tariff Clauses Use Case
Searches regulatory policies and ASHRAE comfort standards.
"""

from typing import Dict, Any
from src.application.services.retrieval_service import RetrievalService

class RetrieveTariffClausesUseCase:
    """Executes hybrid retrieval over regulatory documents."""

    def __init__(self, retrieval_service: RetrievalService):
        self.retrieval_service = retrieval_service

    def execute(self, query: str, top_k: int = 2) -> Dict[str, Any]:
        return self.retrieval_service.search(query=query, top_k=top_k)
