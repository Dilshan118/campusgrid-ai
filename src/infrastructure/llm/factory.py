"""
CampusGrid AI: LLM Provider Factory
Resolves the active LLM provider from settings dynamically.
"""

from typing import Optional
from src.domain.interfaces.llm import LLMProvider
from src.infrastructure.llm.mock_provider import MockLLMProvider
from src.infrastructure.llm.litellm_provider import LiteLLMProvider
from src.config.settings import LLMSettings

class LLMProviderFactory:
    """Factory creating LLMProvider instances based on configuration."""

    @staticmethod
    def create(settings: LLMSettings) -> LLMProvider:
        provider_name = (settings.provider or "mock").lower().strip()

        if provider_name == "mock":
            return MockLLMProvider()

        # liteLLM handles gemini, openai, anthropic, groq, ollama seamlessly
        api_keys = {
            "gemini": settings.gemini_api_key or "",
            "openai": settings.openai_api_key or "",
            "anthropic": settings.anthropic_api_key or "",
            "groq": settings.groq_api_key or ""
        }

        return LiteLLMProvider(
            model=settings.model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            api_keys=api_keys
        )
