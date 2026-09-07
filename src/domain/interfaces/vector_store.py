"""
CampusGrid AI: Abstract Vector Store Interface
Contract for storing and retrieving document vectors (pgvector, ChromaDB, in-memory, Qdrant).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from src.domain.entities.rag import DocumentClause

class VectorSearchResult(BaseModel):
    """Result of vector similarity search."""
    clause: DocumentClause
    similarity: float = Field(..., ge=-1.0, le=1.0)
    distance: Optional[float] = None

class VectorStore(ABC):
    """Abstract interface for vector database storage and similarity search."""

    @abstractmethod
    def add_documents(self, documents: List[DocumentClause]) -> List[str]:
        """Indexes document clauses and returns their stored identifiers."""
        pass

    @abstractmethod
    def similarity_search(
        self,
        query_vector: List[float],
        top_k: int = 2,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[VectorSearchResult]:
        """Performs nearest-neighbor vector similarity search."""
        pass

    @abstractmethod
    def delete(self, document_ids: List[str]) -> bool:
        """Removes specified documents from the vector store."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Returns total number of stored vectors."""
        pass
