"""
CampusGrid AI: Embedding Provider Factory
Resolves the active embedding provider from configuration.
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
        provider_name = (settings.provider or "mock").lower().strip()

        if provider_name == "sentence_transformers":
            if importlib.util.find_spec("sentence_transformers") is not None:
                return SentenceTransformersProvider(model_name=settings.model)
            # /api/health reports the provider actually in use, so this fallback is visible.
            logger.warning(
                "EMBEDDING_PROVIDER=sentence_transformers but the package is not installed "
                "(pip install -e \".[rag]\"); falling back to mock embeddings — dense search is disabled."
            )
        elif provider_name != "mock":
            raise ValueError(f"Unsupported EMBEDDING_PROVIDER '{settings.provider}'. Use 'mock' or 'sentence_transformers'.")

        return MockEmbeddingProvider(dimension=settings.dimension)
