"""
CampusGrid AI: Mock Embedding Provider
Generates deterministic normalized dense vectors for testing and offline execution.
"""

import math
import hashlib
from typing import List
from src.domain.interfaces.embeddings import EmbeddingProvider

class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic, zero-dependency embedding generator based on string hashing."""

    def __init__(self, dimension: int = 384):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def is_semantic(self) -> bool:
        return False

    def _hash_to_vector(self, text: str) -> List[float]:
        """Generates a reproducible, unit-normalized float vector from text."""
        # Use md5 hash rounds to seed floats
        vec = []
        salt = 0
        while len(vec) < self._dimension:
            h = hashlib.md5(f"{text}_{salt}".encode("utf-8")).digest()
            for b in h:
                if len(vec) < self._dimension:
                    vec.append(float(b - 128))
            salt += 1

        # Normalize to unit length for cosine similarity
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [round(x / norm, 6) for x in vec]

    def embed_text(self, text: str) -> List[float]:
        return self._hash_to_vector(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_to_vector(t) for t in texts]
