"""
CampusGrid AI: Google Gemini / Vertex AI Embedding Adapter
Generates dense vector embeddings using Google's text-embedding models
(e.g., 'models/text-embedding-004' or 'models/embedding-001').
Supports both litellm and direct Google Generative Language REST API.
"""

import json
import logging
import os
import threading
import urllib.request
import urllib.error
from collections import OrderedDict
from typing import List, Optional
from src.domain.interfaces.embeddings import EmbeddingProvider
from src.domain.exceptions.base import ProviderException

logger = logging.getLogger("campusgrid.embeddings.google")

_QUERY_CACHE_SIZE = 512


class GoogleEmbeddingProvider(EmbeddingProvider):
    """Google Gemini Embedding Provider. Thread-safe with in-memory caching."""

    def __init__(
        self,
        model: str = "models/text-embedding-004",
        dimension: int = 768,
        api_key: Optional[str] = None,
    ):
        # Normalize model string
        clean_model = model.strip()
        if clean_model.startswith("gemini/"):
            clean_model = clean_model.replace("gemini/", "", 1)
        if not clean_model.startswith("models/"):
            clean_model = f"models/{clean_model}"

        # Map legacy model names to current Gemini API embedding model
        if clean_model in ("models/embedding-001", "models/text-embedding-001", "models/gemini-embedding"):
            clean_model = "models/gemini-embedding-001"

        self.model_name = clean_model
        self._dimension = dimension
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self._cache: "OrderedDict[str, List[float]]" = OrderedDict()
        self._cache_lock = threading.Lock()

    def _get_api_key(self) -> str:
        key = self.api_key or os.getenv("GEMINI_API_KEY", "")
        if not key:
            raise ProviderException(
                message="Google embedding requires GEMINI_API_KEY. Please set GEMINI_API_KEY in your .env file.",
                provider_name="google"
            )
        return key

    def warm_up(self) -> None:
        """Validates the API key, network path and vector size at startup.

        Raises ProviderException on any failure, so EmbeddingProviderFactory can fall back to the
        mock provider at startup instead of every later search failing at request time."""
        self._get_api_key()
        self.embed_text("CampusGrid test initialization")

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def is_semantic(self) -> bool:
        return True

    def _call_google_api(self, endpoint: str, payload: dict) -> dict:
        api_key = self._get_api_key()
        url = f"https://generativelanguage.googleapis.com/v1beta/{self.model_name}:{endpoint}?key={api_key}"
        headers = {"Content-Type": "application/json"}
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = resp.read().decode("utf-8")
                return json.loads(resp_data)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise ProviderException(
                message=f"Google Embedding API error HTTP {e.code}: {err_body}",
                provider_name="google"
            ) from e
        except Exception as e:
            raise ProviderException(
                message=f"Failed to connect to Google Embedding API: {str(e)}",
                provider_name="google"
            ) from e

    def embed_text(self, text: str) -> List[float]:
        with self._cache_lock:
            cached = self._cache.get(text)
            if cached is not None:
                self._cache.move_to_end(text)
                return list(cached)

        # Direct Google Generative Language API with explicit outputDimensionality
        embedding: Optional[List[float]] = None
        try:
            payload = {
                "model": self.model_name,
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": self._dimension,
            }
            res_data = self._call_google_api("embedContent", payload)
            if "embedding" in res_data and "values" in res_data["embedding"]:
                embedding = res_data["embedding"]["values"]
            else:
                raise ProviderException(
                    message=f"Unexpected response format from Google Embeddings: {res_data}",
                    provider_name="google"
                )
        except Exception as e:
            # Fall back to LiteLLM if direct REST fails
            try:
                import litellm
                api_key = self._get_api_key()
                litellm_model = f"gemini/{self.model_name.replace('models/', '')}"
                res = litellm.embedding(model=litellm_model, input=[text], api_key=api_key)
                embedding = res.data[0]["embedding"]
            except Exception:
                raise e

        # A vector of another size would be written into (or compared against) a column of the
        # configured size; refuse it rather than silently changing the provider's dimension.
        if not embedding or len(embedding) != self._dimension:
            raise ProviderException(
                message=(
                    f"Google embedding returned {len(embedding or [])} dimensions; EMBEDDING_DIMENSION is "
                    f"{self._dimension}. Use a model that supports outputDimensionality or change the setting."
                ),
                provider_name="google",
            )

        with self._cache_lock:
            self._cache[text] = embedding
            if len(self._cache) > _QUERY_CACHE_SIZE:
                self._cache.popitem(last=False)

        return list(embedding)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        # Direct REST batchEmbedContents (chunked by 50 to obey Google limits) with outputDimensionality
        results: List[List[float]] = []
        batch_size = 50
        for i in range(0, len(texts), batch_size):
            chunk = texts[i:i + batch_size]
            payload = {
                "requests": [
                    {
                        "model": self.model_name,
                        "content": {"parts": [{"text": t}]},
                        "outputDimensionality": self._dimension,
                    }
                    for t in chunk
                ]
            }
            try:
                res_data = self._call_google_api("batchEmbedContents", payload)
                embeddings = res_data.get("embeddings", [])
                for item in embeddings:
                    results.append(item.get("values", []))
            except Exception:
                # Per-item fallback if batch fails
                for t in chunk:
                    results.append(self.embed_text(t))

        return results
