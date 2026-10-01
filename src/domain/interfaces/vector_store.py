"""
CampusGrid AI: Abstract Vector Store Interface
Contract for storing and retrieving document vectors (pgvector, ChromaDB, in-memory, Qdrant).
"""

import math
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from src.domain.entities.rag import DocumentClause
from src.domain.exceptions.base import VectorStoreException

# No embedding model in use is anywhere near this; anything longer is malformed or hostile input.
MAX_VECTOR_DIMENSION = 8192


def validate_vector(vector: Any, expected_dimension: Optional[int], provider_name: str) -> List[float]:
    """Rejects a vector that is empty, too long, not all finite numbers, or not of the store's size.

    Every adapter calls this at its boundary, so a malformed query fails loudly instead of being
    scored as "similarity 0.0" (indistinguishable from a genuine no-match) or burning CPU on an
    oversized input."""
    if not isinstance(vector, (list, tuple)) or not vector:
        raise VectorStoreException("Vector must be a non-empty list of numbers.", provider_name=provider_name)
    if len(vector) > MAX_VECTOR_DIMENSION:
        raise VectorStoreException(
            f"Vector has {len(vector)} dimensions; the maximum accepted is {MAX_VECTOR_DIMENSION}.",
            provider_name=provider_name,
            details={"dimension": len(vector)},
        )
    if expected_dimension is not None and len(vector) != expected_dimension:
        raise VectorStoreException(
            f"Vector has {len(vector)} dimensions but the store holds {expected_dimension}-dimensional "
            "embeddings. Re-index the corpus after changing the embedding model.",
            provider_name=provider_name,
            details={"dimension": len(vector), "expected_dimension": expected_dimension},
        )
    try:
        values = [float(x) for x in vector]
    except (TypeError, ValueError):
        raise VectorStoreException("Vector contains a non-numeric value.", provider_name=provider_name)
    if not all(math.isfinite(x) for x in values):
        raise VectorStoreException("Vector contains NaN or infinite values.", provider_name=provider_name)
    return values

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

    def list_documents(self) -> List[DocumentClause]:
        """Returns every stored clause (without embeddings). Used to rebuild the keyword index
        on startup when the vector store is persistent (pgvector, Chroma)."""
        raise NotImplementedError(f"{type(self).__name__} does not support list_documents()")
