"""
CampusGrid AI: SentenceTransformers Embedding Adapter
Generates dense vector embeddings using local Hugging Face / SentenceTransformers models.
"""

import threading
from collections import OrderedDict
from typing import List
from src.domain.interfaces.embeddings import EmbeddingProvider
from src.domain.exceptions.base import ProviderException

# Query texts repeat a lot (Agent 3 runs the same constraint queries for every plan).
_QUERY_CACHE_SIZE = 512


class SentenceTransformersProvider(EmbeddingProvider):
    """Local SentenceTransformers model embedding generator. Safe to share across request threads."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._dimension = 384
        self._load_lock = threading.Lock()
        self._cache: "OrderedDict[str, List[float]]" = OrderedDict()
        self._cache_lock = threading.Lock()

    def _get_model(self):
        if self._model is None:
            with self._load_lock:  # two concurrent first requests must not both load the model
                if self._model is None:
                    try:
                        from sentence_transformers import SentenceTransformer
                        try:
                            # Use the downloaded copy without contacting the Hugging Face Hub...
                            model = SentenceTransformer(self.model_name, local_files_only=True)
                        except Exception:
                            # ...and download it only the first time.
                            model = SentenceTransformer(self.model_name)
                        get_dim = getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension
                        self._dimension = get_dim()
                        self._model = model
                    except Exception as e:
                        raise ProviderException(
                            message=f"Failed to load SentenceTransformer model '{self.model_name}': {str(e)}",
                            provider_name="sentence-transformers"
                        ) from e
        return self._model

    def warm_up(self) -> None:
        """Loads the model eagerly so a missing model is discovered at startup."""
        self._get_model()

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_text(self, text: str) -> List[float]:
        with self._cache_lock:
            cached = self._cache.get(text)
            if cached is not None:
                self._cache.move_to_end(text)
                return list(cached)
        embedding = self._get_model().encode(text, normalize_embeddings=True).tolist()
        with self._cache_lock:
            self._cache[text] = embedding
            if len(self._cache) > _QUERY_CACHE_SIZE:
                self._cache.popitem(last=False)
        return list(embedding)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        model = self._get_model()
        embeddings = model.encode(texts, normalize_embeddings=True)
        return [e.tolist() for e in embeddings]
