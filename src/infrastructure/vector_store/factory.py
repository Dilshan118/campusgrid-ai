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
    """Factory creating VectorStore instances based on configuration.

    A setting that cannot be honoured stops startup with a clear message rather than silently
    falling back to the in-memory store (which loses every uploaded clause on restart).
    """

    @staticmethod
    def create(settings: VectorStoreSettings, engine=None) -> VectorStore:
        provider_name = (settings.provider or "memory").lower().strip()

        if provider_name == "memory":
            return MemoryVectorStore()
        if provider_name == "chroma":
            return ChromaStore(persist_dir=settings.persist_dir)
        if provider_name == "pgvector":
            if engine is None:
                raise ValueError(
                    "VECTOR_STORE_PROVIDER=pgvector needs DATABASE_PROVIDER=postgres (pgvector lives in that database)."
                )
            return PgVectorStore(engine=engine)
        raise ValueError(
            f"VECTOR_STORE_PROVIDER='{settings.provider}' is not supported. Use 'memory', 'pgvector' or 'chroma'."
        )
