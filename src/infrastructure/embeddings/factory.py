"""
CampusGrid AI: Embedding Provider Factory
Resolves the active embedding provider from configuration.

'auto' (the default) and 'sentence_transformers' both try the real model and fall back to the
deterministic mock if the package is missing or the model cannot be loaded (for example offline
on a machine that has never downloaded it). /api/health reports which provider is actually live.
"""

import importlib.util
import logging
from src.domain.interfaces.embeddings import EmbeddingProvider
from src.infrastructure.embeddings.mock_embeddings import MockEmbeddingProvider
from src.infrastructure.embeddings.sentence_transformers import SentenceTransformersProvider
from src.config.settings import EmbeddingSettings

logger = logging.getLogger("campusgrid.embeddings")


class EmbeddingProviderFactory:
    """Factory creating EmbeddingProvider instances based on configuration."""

    @staticmethod
    def create(settings: EmbeddingSettings) -> EmbeddingProvider:
        provider_name = (settings.provider or "auto").lower().strip()

        if provider_name == "mock":
            return MockEmbeddingProvider(dimension=settings.dimension)
        if provider_name not in ("auto", "sentence_transformers"):
            raise ValueError(
                f"Unsupported EMBEDDING_PROVIDER '{settings.provider}'. Use 'auto', 'sentence_transformers' or 'mock'."
            )

        if importlib.util.find_spec("sentence_transformers") is None:
            logger.warning(
                "sentence-transformers is not installed (pip install -e \".[rag]\"); "
                "using mock embeddings — semantic search is disabled."
            )
            return MockEmbeddingProvider(dimension=settings.dimension)

        provider = SentenceTransformersProvider(model_name=settings.model)
        try:
            provider.warm_up()  # load now, so a missing model degrades at startup instead of failing a request
        except Exception as exc:
            logger.warning("Embedding model '%s' could not be loaded (%s); using mock embeddings.", settings.model, exc)
            return MockEmbeddingProvider(dimension=settings.dimension)

        if provider.dimension != settings.dimension:
            logger.warning(
                "Embedding model produces %d-dimensional vectors but EMBEDDING_DIMENSION is %d; "
                "the pgvector column in init.sql must match the model.", provider.dimension, settings.dimension,
            )
        return provider
