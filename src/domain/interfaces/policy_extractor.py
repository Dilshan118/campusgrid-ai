"""
CampusGrid AI: Regulatory Policy & Tariff Rule Extraction Domain Interfaces
Assigned to: Member 1 (Team Lead - Information Retrieval & Regulatory RAG)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from src.domain.entities.rag import RetrievedChunk

class RegulatoryRuleExtractorInterface(ABC):
    """Abstract interface for extracting structured tariff figures and regulatory limits from policy text."""

    @abstractmethod
    def extract_tariff_rules(self, text: str) -> Dict[str, Any]:
        """
        Parses policy document text and extracts Time-of-Use rates, peak surcharge limits,
        and ASHRAE thermal comfort envelopes.
        """
        pass


class PolicySearchEngineInterface(ABC):
    """Abstract interface for hybrid semantic search over institutional energy documents."""

    @abstractmethod
    def search(self, query: str, top_k: int = 3) -> List[RetrievedChunk]:
        """Executes hybrid dense + BM25 search and returns ranked policy clauses with citations."""
        pass
