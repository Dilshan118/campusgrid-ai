"""
CampusGrid AI: Abstract Reranker Interface
Contract for reranking retrieved candidate passages (RRF, Cross-Encoder, etc.).
"""

from abc import ABC, abstractmethod
from typing import List
from pydantic import BaseModel, Field
from src.domain.entities.rag import DocumentClause

class RerankResult(BaseModel):
    clause: DocumentClause
    score: float
    rank: int

class Reranker(ABC):
    """Abstract interface for candidate reranking."""

    @abstractmethod
    def rerank(self, query: str, candidates: List[DocumentClause], top_k: int = 2) -> List[RerankResult]:
        pass
