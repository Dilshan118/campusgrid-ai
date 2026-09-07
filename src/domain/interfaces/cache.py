"""
CampusGrid AI: Abstract Cache Provider Interface
Contract for caching hot telemetry, weather forecasts, and LLM responses.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

class CacheProvider(ABC):
    """Abstract caching contract."""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        pass

    @abstractmethod
    def clear(self) -> bool:
        pass
