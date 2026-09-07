"""
CampusGrid AI: Embedding Provider Factory
Resolves the active embedding provider from configuration.
"""

from src.domain.interfaces.embeddings import EmbeddingProvider
from src.infrastructure.embeddings.mock_embeddings import MockEmbeddingProvider
from src.infrastructure.embeddings.sentence_transformers import SentenceTransformersProvider
from src.config.settings import EmbeddingSettings

class EmbeddingProviderFactory:
    """Factory creating EmbeddingProvider instances based on configuration."""

    @staticmethod
    def create(settings: EmbeddingSettings) -> EmbeddingProvider:
        provider_name = (settings.provider or "mock").lower().strip()

        if provider_name == "sentence_transformers":
            return SentenceTransformersProvider(model_name=settings.model)

        return MockEmbeddingProvider(dimension=settings.dimension)
