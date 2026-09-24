"""
CampusGrid AI: Abstract Keyword (Sparse) Search Interface
Contract for lexical retrieval engines such as Okapi BM25, so the retrieval service
depends on an interface rather than on a concrete infrastructure class.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple
from src.domain.entities.rag import DocumentClause


class KeywordSearchEngine(ABC):
    """Abstract interface for sparse keyword retrieval over document clauses."""

    @abstractmethod
    def index_documents(self, documents: List[DocumentClause]) -> None:
        """Replaces the whole index with the given clauses."""
        pass

    @abstractmethod
    def add_documents(self, documents: List[DocumentClause]) -> None:
        """Adds clauses to the existing index."""
        pass

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> List[Tuple[DocumentClause, float]]:
        pass

    @property
    @abstractmethod
    def documents(self) -> List[DocumentClause]:
        """Every clause currently indexed."""
        pass
