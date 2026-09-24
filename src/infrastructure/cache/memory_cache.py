"""
CampusGrid AI: In-Memory TTL Cache Provider
Thread-safe, expiring in-memory cache for telemetry readings, weather forecasts and search results.
"""

import threading
import time
from typing import Any, Optional, Dict, Tuple
from src.domain.interfaces.cache import CacheProvider

class MemoryCacheProvider(CacheProvider):
    """Simple in-memory cache with TTL support, safe to share across request threads."""

    def __init__(self, default_ttl_seconds: int = 300, max_entries: int = 5000):
        self.default_ttl = default_ttl_seconds
        self.max_entries = max_entries
        self._store: Dict[str, Tuple[Any, Optional[float]]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            val, expiry = entry
            if expiry is not None and time.time() > expiry:
                del self._store[key]
                return None
            return val

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        expiry = time.time() + ttl if ttl and ttl > 0 else None
        with self._lock:
            if len(self._store) >= self.max_entries and key not in self._store:
                self._store.pop(next(iter(self._store)))  # drop the oldest entry
            self._store[key] = (value, expiry)
        return True

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._store.pop(key, None) is not None

    def clear(self) -> bool:
        with self._lock:
            self._store.clear()
        return True
