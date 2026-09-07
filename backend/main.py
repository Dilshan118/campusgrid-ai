"""
CampusGrid AI: Backend Entry Point (Backwards-Compatibility Shim)
Re-exports the modular multi-agent FastAPI application from src.api.main.
Ensures zero-downtime compatibility with existing scripts and development runners.
"""

from src.api.main import app

__all__ = ["app"]

