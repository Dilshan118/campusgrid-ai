"""
CampusGrid AI: Core Configuration Manager (Backwards-Compatibility Shim)
Re-exports modular settings from src.config.settings.
"""

from src.config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
