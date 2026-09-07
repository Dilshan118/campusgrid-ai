"""
CampusGrid AI: Prompt Template Manager
Loads, caches, and renders externalized prompt templates with strict parameter substitution.
"""

import os
from typing import Dict, Any, Optional

class PromptManager:
    """Manages versioned, external prompt template files."""

    def __init__(self, templates_dir: Optional[str] = None):
        if templates_dir:
            self.templates_dir = templates_dir
        else:
            self.templates_dir = os.path.join(os.path.dirname(__file__))
        self._cache: Dict[str, str] = {}

    def get_template(self, relative_path: str) -> str:
        """Reads and caches template text from disk."""
        if relative_path in self._cache:
            return self._cache[relative_path]

        full_path = os.path.join(self.templates_dir, relative_path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Prompt template file not found at: {full_path}")

        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()

        self._cache[relative_path] = content
        return content

    def render(self, relative_path: str, **kwargs) -> str:
        """Renders a template by safely substituting keyword arguments."""
        template = self.get_template(relative_path)
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing required parameter {e} for prompt template: {relative_path}")

_default_manager: Optional[PromptManager] = None

def get_prompt_manager() -> PromptManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = PromptManager()
    return _default_manager
