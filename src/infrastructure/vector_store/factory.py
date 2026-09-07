"""
CampusGrid AI: Vector Store Factory
Resolves the active VectorStore implementation from configuration.
"""

from typing import Optional
from src.domain.interfaces.vector_store import VectorStore
from src.infrastructure.vector_store.memory_store import MemoryVectorStore
from src.infrastructure.vector_store.pgvector_store import PgVectorStore
from src.infrastructure.vector_store.chroma_store import ChromaStore
from src.config.settings import VectorStoreSettings

class VectorStoreFactory:
    """Factory creating VectorStore instances based on configuration."""

    @staticmethod
    def create(settings: VectorStoreSettings, engine=None) -> VectorStore:
        provider_name = (settings.provider or "memory").lower().strip()

        if provider_name == "pgvector" and engine is not None:
            return PgVectorStore(engine=engine)
        elif provider_name == "chroma":
            return ChromaStore(persist_dir=settings.persist_dir)

        # Default fallback is always in-memory
        return MemoryVectorStore()
