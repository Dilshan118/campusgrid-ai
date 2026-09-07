"""
CampusGrid AI: Cache Provider Factory
Resolves the active CacheProvider instance from configuration.
"""

from src.domain.interfaces.cache import CacheProvider
from src.infrastructure.cache.memory_cache import MemoryCacheProvider
from src.config.settings import CacheSettings

class CacheProviderFactory:
    """Factory creating CacheProvider instances based on configuration."""

    @staticmethod
    def create(settings: CacheSettings) -> CacheProvider:
        # Defaults to in-memory cache
        return MemoryCacheProvider(default_ttl_seconds=settings.ttl_seconds)
