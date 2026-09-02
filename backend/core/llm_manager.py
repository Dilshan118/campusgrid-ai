"""
CampusGrid AI: Pluggable LLM Manager & Factory
Enables zero-code switching between Google Gemini, OpenAI, Anthropic, Groq, and Ollama
driven entirely by environment variables in .env.
"""

import os
from typing import List, Dict, Any, Optional
import litellm
from backend.core.config import get_settings

settings = get_settings()

class LLMManager:
    """
    Unified LLM provider manager.
    Injects appropriate API keys dynamically based on active configuration.
    """
    def __init__(self):
        self._configure_credentials()

    def _configure_credentials(self):
        """Sets required environment variables for LiteLLM based on settings."""
        if settings.gemini_api_key:
            os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
        if settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key
        if settings.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
        if settings.groq_api_key:
            os.environ["GROQ_API_KEY"] = settings.groq_api_key

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model_override: Optional[str] = None
    ) -> str:
        """
        Executes an LLM chat completion using the model specified in .env.
        
        Args:
            messages: List of message dictionaries [{"role": "system", "content": ...}, {"role": "user", "content": ...}]
            temperature: Sampling temperature (defaults to config)
            max_tokens: Maximum tokens to generate (defaults to config)
            model_override: Optional override (e.g., for specific sub-agent tasks)
            
        Returns:
            The generated string response.
        """
        target_model = model_override or settings.llm_model
        temp = temperature if temperature is not None else settings.llm_temperature
        tokens = max_tokens if max_tokens is not None else settings.llm_max_tokens

        response = litellm.completion(
            model=target_model,
            messages=messages,
            temperature=temp,
            max_tokens=tokens,
        )

        return response.choices[0].message.content

    def get_active_model_info(self) -> Dict[str, Any]:
        """Returns metadata about the active LLM provider and model."""
        return {
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens
        }

# Global singleton instance
llm_manager = LLMManager()

def get_llm() -> LLMManager:
    """Dependency / accessor for the global LLM manager."""
    return llm_manager
