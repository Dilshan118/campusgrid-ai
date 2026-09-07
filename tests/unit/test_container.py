"""
Unit tests for Dependency Injection Container and provider switching.
"""

from src.config.settings import Settings
from src.application.container import Container
from src.infrastructure.llm.mock_provider import MockLLMProvider
from src.infrastructure.vector_store.memory_store import MemoryVectorStore
from src.infrastructure.cache.memory_cache import MemoryCacheProvider

def test_container_mock_providers():
    settings = Settings(
        llm_provider="mock",
        vector_store_provider="memory",
        database_provider="in_memory",
        cache_provider="memory"
    )
    container = Container(settings)

    assert isinstance(container.llm_provider, MockLLMProvider)
    assert isinstance(container.vector_store, MemoryVectorStore)
    assert isinstance(container.cache_provider, MemoryCacheProvider)
    assert container.orchestrator is not None
