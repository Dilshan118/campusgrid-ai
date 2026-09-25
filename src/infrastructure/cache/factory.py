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
        provider_name = (settings.provider or "memory").lower().strip()
        if provider_name == "memory":
            return MemoryCacheProvider(default_ttl_seconds=settings.ttl_seconds)
        # Previously every value (including 'redis') silently produced the in-memory cache.
        raise ValueError(
            f"CACHE_PROVIDER='{settings.provider}' is not implemented; only 'memory' is supported."
        )
