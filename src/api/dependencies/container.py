"""
CampusGrid AI: FastAPI Route Dependencies
Injects application container and services into API endpoints.
"""

from fastapi import Depends
from src.application.container import Container, get_container

def get_app_container() -> Container:
    """FastAPI dependency for accessing the application container."""
    return get_container()
