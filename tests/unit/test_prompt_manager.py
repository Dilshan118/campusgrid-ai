"""
Unit tests for external PromptManager and template rendering.
"""

import pytest
from src.prompts.manager import PromptManager

def test_prompt_manager_rendering():
    pm = PromptManager()
    rendered = pm.render(
        "system/base_system.txt"
    )
    assert "Golden Safety Rules" in rendered
    assert "CEB" in rendered or "PUCSL" in rendered

def test_prompt_manager_missing_variable_raises():
    pm = PromptManager()
    with pytest.raises(ValueError):
        # Missing required parameter {user_query}
        pm.render("agents/coordinator/intent_extraction.txt")
