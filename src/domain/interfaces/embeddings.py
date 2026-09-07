"""
CampusGrid AI: Abstract Embedding Provider Interface
Contract for generating dense vector embeddings from text passages and queries.
"""

from abc import ABC, abstractmethod
from typing import List

class EmbeddingProvider(ABC):
    """Abstract interface for text embedding generation."""

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generates a dense embedding vector for a single string."""
        pass

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generates dense embedding vectors for a batch of strings."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Returns the dimensionality of the generated vectors (e.g., 384 or 1536)."""
        pass
