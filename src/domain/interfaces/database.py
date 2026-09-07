"""
CampusGrid AI: Abstract Database Session Contract
Abstracts relational session acquisition and transaction management.
"""

from abc import ABC, abstractmethod
from typing import Generator, Any

class DatabaseSessionManager(ABC):
    """Abstract manager for relational database sessions."""

    @abstractmethod
    def get_session(self) -> Generator[Any, None, None]:
        pass

    @abstractmethod
    def init_database(self) -> None:
        pass
