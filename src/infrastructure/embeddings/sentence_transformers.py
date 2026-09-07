"""
CampusGrid AI: SentenceTransformers Embedding Adapter
Generates dense vector embeddings using local Hugging Face / SentenceTransformers models.
"""

from typing import List, Optional
from src.domain.interfaces.embeddings import EmbeddingProvider
from src.domain.exceptions.base import ProviderException

class SentenceTransformersProvider(EmbeddingProvider):
    """Local SentenceTransformers model embedding generator."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._dimension = 384

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                self._dimension = self._model.get_sentence_embedding_dimension()
            except Exception as e:
                raise ProviderException(
                    message=f"Failed to load SentenceTransformer model '{self.model_name}': {str(e)}",
                    provider_name="sentence-transformers"
                ) from e
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_text(self, text: str) -> List[float]:
        model = self._get_model()
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        model = self._get_model()
        embeddings = model.encode(texts, normalize_embeddings=True)
        return [e.tolist() for e in embeddings]
