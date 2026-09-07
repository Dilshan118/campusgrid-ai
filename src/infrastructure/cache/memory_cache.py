"""
CampusGrid AI: In-Memory TTL Cache Provider
Thread-safe, expiring in-memory cache for telemetry readings and weather forecasts.
"""

import time
from typing import Any, Optional, Dict, Tuple
from src.domain.interfaces.cache import CacheProvider

class MemoryCacheProvider(CacheProvider):
    """Simple in-memory cache with TTL support."""

    def __init__(self, default_ttl_seconds: int = 300):
        self.default_ttl = default_ttl_seconds
        self._store: Dict[str, Tuple[Any, Optional[float]]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key not in self._store:
            return None
        val, expiry = self._store[key]
        if expiry is not None and time.time() > expiry:
            del self._store[key]
            return None
        return val

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        expiry = time.time() + ttl if ttl and ttl > 0 else None
        self._store[key] = (value, expiry)
        return True

    def delete(self, key: str) -> bool:
        return self._store.pop(key, None) is not None

    def clear(self) -> bool:
        self._store.clear()
        return True
