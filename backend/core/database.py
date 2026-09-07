"""
CampusGrid AI: Database Connection Manager (Backwards-Compatibility Shim)
Re-exports database engine and session generator from src.application.container.
"""

from typing import Generator
from src.application.container import get_container

container = get_container()
engine = container.session_manager.engine if container.session_manager else None

def init_db():
    if container.session_manager:
        container.session_manager.init_database()

def get_session():
    if container.session_manager:
        yield from container.session_manager.get_session()
    else:
        yield None

__all__ = ["engine", "init_db", "get_session"]
