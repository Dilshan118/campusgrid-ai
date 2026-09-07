"""
CampusGrid AI: Pluggable LLM Manager (Backwards-Compatibility Shim)
Delegates to the modular LLMProvider from src.application.container.
"""

from typing import List, Dict, Any, Optional
from src.application.container import get_container
from src.domain.interfaces.llm import LLMMessage

class LLMManager:
    """Backwards-compatible LLMManager delegating to active LLMProvider."""

    def __init__(self):
        self.container = get_container()

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model_override: Optional[str] = None
    ) -> str:
        domain_messages = [LLMMessage(role=m["role"], content=m["content"]) for m in messages]
        res = self.container.llm_provider.generate(
            messages=domain_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            model_override=model_override
        )
        return res.content

    def get_active_model_info(self) -> Dict[str, Any]:
        return self.container.llm_provider.get_model_info()

llm_manager = LLMManager()

def get_llm() -> LLMManager:
    return llm_manager

__all__ = ["LLMManager", "llm_manager", "get_llm"]
