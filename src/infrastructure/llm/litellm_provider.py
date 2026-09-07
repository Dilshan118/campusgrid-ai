"""
CampusGrid AI: LiteLLM Multi-Provider Adapter
Pluggable adapter for Google Gemini, OpenAI, Claude, Groq, and Ollama using LiteLLM.
"""

import time
import os
from typing import List, Dict, Any, Optional
from src.domain.interfaces.llm import LLMProvider, LLMMessage, LLMResponse
from src.domain.exceptions.base import LLMProviderException

class LiteLLMProvider(LLMProvider):
    """LiteLLM Provider Adapter implementing LLMProvider."""

    def __init__(
        self,
        model: str = "gemini/gemini-1.5-flash",
        temperature: float = 0.2,
        max_tokens: int = 1500,
        api_keys: Optional[Dict[str, str]] = None
    ):
        self.default_model = model
        self.default_temperature = temperature
        self.default_max_tokens = max_tokens
        self.api_keys = api_keys or {}
        self._setup_credentials()

    def _setup_credentials(self):
        """Sets credentials into environment for LiteLLM if provided."""
        for key, val in self.api_keys.items():
            if val:
                env_key = f"{key.upper()}_API_KEY" if not key.upper().endswith("_API_KEY") else key.upper()
                os.environ[env_key] = val

    def generate(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model_override: Optional[str] = None
    ) -> LLMResponse:
        import litellm
        start_time = time.time()
        target_model = model_override or self.default_model
        temp = temperature if temperature is not None else self.default_temperature
        tokens = max_tokens if max_tokens is not None else self.default_max_tokens

        formatted_messages = [{"role": m.role, "content": m.content} for m in messages]

        try:
            response = litellm.completion(
                model=target_model,
                messages=formatted_messages,
                temperature=temp,
                max_tokens=tokens,
            )
            latency = (time.time() - start_time) * 1000.0

            choice = response.choices[0]
            content = choice.message.content or ""
            usage = getattr(response, "usage", None)

            return LLMResponse(
                content=content,
                model=target_model,
                provider="litellm",
                tokens_prompt=getattr(usage, "prompt_tokens", None) if usage else None,
                tokens_completion=getattr(usage, "completion_tokens", None) if usage else None,
                total_tokens=getattr(usage, "total_tokens", None) if usage else None,
                latency_ms=latency,
                finish_reason=getattr(choice, "finish_reason", "stop")
            )
        except Exception as e:
            raise LLMProviderException(
                message=f"LiteLLM completion call failed: {str(e)}",
                provider_name="litellm",
                details={"model": target_model, "original_error": str(e)}
            ) from e

    async def generate_async(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model_override: Optional[str] = None
    ) -> LLMResponse:
        import litellm
        start_time = time.time()
        target_model = model_override or self.default_model
        temp = temperature if temperature is not None else self.default_temperature
        tokens = max_tokens if max_tokens is not None else self.default_max_tokens

        formatted_messages = [{"role": m.role, "content": m.content} for m in messages]

        try:
            response = await litellm.acompletion(
                model=target_model,
                messages=formatted_messages,
                temperature=temp,
                max_tokens=tokens,
            )
            latency = (time.time() - start_time) * 1000.0
            choice = response.choices[0]
            content = choice.message.content or ""
            usage = getattr(response, "usage", None)

            return LLMResponse(
                content=content,
                model=target_model,
                provider="litellm",
                tokens_prompt=getattr(usage, "prompt_tokens", None) if usage else None,
                tokens_completion=getattr(usage, "completion_tokens", None) if usage else None,
                total_tokens=getattr(usage, "total_tokens", None) if usage else None,
                latency_ms=latency,
                finish_reason=getattr(choice, "finish_reason", "stop")
            )
        except Exception as e:
            raise LLMProviderException(
                message=f"LiteLLM async completion call failed: {str(e)}",
                provider_name="litellm",
                details={"model": target_model, "original_error": str(e)}
            ) from e

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "provider": "litellm",
            "model": self.default_model,
            "temperature": self.default_temperature,
            "max_tokens": self.default_max_tokens
        }
