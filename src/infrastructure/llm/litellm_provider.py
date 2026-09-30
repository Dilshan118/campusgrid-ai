"""
CampusGrid AI: LiteLLM Multi-Provider Adapter
Pluggable adapter for Google Gemini, OpenAI, Claude, Groq, and Ollama using LiteLLM.
"""

import time
import os
from typing import List, Dict, Any, Optional
from src.domain.interfaces.llm import LLMProvider, LLMMessage, LLMResponse
from src.domain.exceptions.base import LLMProviderException
from src.infrastructure.observability.tracer import Tracer

def _patch_litellm_compat():
    """Ensure litellm works cleanly with Python 3.10 and Pydantic 2.13+."""
    import typing
    if not hasattr(typing, "NotRequired"):
        try:
            import typing_extensions
            typing.NotRequired = typing_extensions.NotRequired
        except ImportError:
            pass
    try:
        import litellm.types.utils as l_utils
        if not hasattr(l_utils, "ChatCompletionReasoningSummaryTextBlock"):
            l_utils.ChatCompletionReasoningSummaryTextBlock = typing.Any
        for model_cls in (getattr(l_utils, "Message", None), getattr(l_utils, "Choices", None), getattr(l_utils, "ModelResponse", None)):
            if model_cls and hasattr(model_cls, "model_rebuild"):
                try:
                    model_cls.model_rebuild()
                except Exception:
                    pass
    except Exception:
        pass


class LiteLLMProvider(LLMProvider):
    """LiteLLM Provider Adapter implementing LLMProvider."""

    def __init__(
        self,
        model: str = "gemini/gemini-1.5-flash",
        temperature: float = 0.2,
        max_tokens: int = 1500,
        api_keys: Optional[Dict[str, str]] = None,
        timeout_seconds: float = 30.0,
        num_retries: int = 2,
    ):
        self.default_model = model
        self.default_temperature = temperature
        self.default_max_tokens = max_tokens
        self.api_keys = api_keys or {}
        # Without a timeout a stalled provider holds a request thread for LiteLLM's 10-minute default.
        self.timeout_seconds = timeout_seconds
        self.num_retries = num_retries
        self._setup_credentials()

    def _setup_credentials(self):
        """Sets credentials into environment for LiteLLM if provided."""
        for key, val in self.api_keys.items():
            if val:
                env_key = f"{key.upper()}_API_KEY" if not key.upper().endswith("_API_KEY") else key.upper()
                os.environ[env_key] = val


    def _call_groq_direct(
        self,
        messages: List[Dict[str, str]],
        temp: float,
        tokens: int,
        target_model: str,
        start_time: float
    ) -> LLMResponse:
        from groq import Groq
        groq_api_key = self.api_keys.get("groq") or os.environ.get("GROQ_API_KEY")
        client = Groq(api_key=groq_api_key)
        raw_model = target_model.replace("groq/", "")
        try:
            completion = client.chat.completions.create(
                model=raw_model,
                messages=messages,
                temperature=temp,
                max_tokens=tokens,
                timeout=self.timeout_seconds,
            )
        except Exception as err:
            if "model_not_found" in str(err) or "does not exist" in str(err):
                raw_model = "qwen/qwen3.8-27b"
                completion = client.chat.completions.create(
                    model=raw_model,
                    messages=messages,
                    temperature=temp,
                    max_tokens=tokens,
                    timeout=self.timeout_seconds,
                )
            else:
                raise err

        latency = (time.time() - start_time) * 1000.0
        choice = completion.choices[0]
        content = choice.message.content or ""
        usage = getattr(completion, "usage", None)
        self._log_usage(f"groq/{raw_model}", usage, latency)

        return LLMResponse(
            content=content,
            model=f"groq/{raw_model}",
            provider="groq",
            tokens_prompt=getattr(usage, "prompt_tokens", None) if usage else None,
            tokens_completion=getattr(usage, "completion_tokens", None) if usage else None,
            total_tokens=getattr(usage, "total_tokens", None) if usage else None,
            latency_ms=latency,
            finish_reason=getattr(choice, "finish_reason", "stop")
        )

    async def _call_groq_direct_async(
        self,
        messages: List[Dict[str, str]],
        temp: float,
        tokens: int,
        target_model: str,
        start_time: float
    ) -> LLMResponse:
        from groq import AsyncGroq
        groq_api_key = self.api_keys.get("groq") or os.environ.get("GROQ_API_KEY")
        client = AsyncGroq(api_key=groq_api_key)
        raw_model = target_model.replace("groq/", "")
        try:
            completion = await client.chat.completions.create(
                model=raw_model,
                messages=messages,
                temperature=temp,
                max_tokens=tokens,
                timeout=self.timeout_seconds,
            )
        except Exception as err:
            if "model_not_found" in str(err) or "does not exist" in str(err):
                raw_model = "qwen/qwen3.8-27b"
                completion = await client.chat.completions.create(
                    model=raw_model,
                    messages=messages,
                    temperature=temp,
                    max_tokens=tokens,
                    timeout=self.timeout_seconds,
                )
            else:
                raise err

        latency = (time.time() - start_time) * 1000.0
        choice = completion.choices[0]
        content = choice.message.content or ""
        usage = getattr(completion, "usage", None)
        self._log_usage(f"groq/{raw_model}", usage, latency)

        return LLMResponse(
            content=content,
            model=f"groq/{raw_model}",
            provider="groq",
            tokens_prompt=getattr(usage, "prompt_tokens", None) if usage else None,
            tokens_completion=getattr(usage, "completion_tokens", None) if usage else None,
            total_tokens=getattr(usage, "total_tokens", None) if usage else None,
            latency_ms=latency,
            finish_reason=getattr(choice, "finish_reason", "stop")
        )

    def generate(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model_override: Optional[str] = None
    ) -> LLMResponse:
        start_time = time.time()
        target_model = model_override or self.default_model
        temp = temperature if temperature is not None else self.default_temperature
        tokens = max_tokens if max_tokens is not None else self.default_max_tokens

        formatted_messages = [{"role": m.role, "content": m.content} for m in messages]

        # Use native Groq client if Groq model requested
        if target_model.startswith("groq/") or "groq" in target_model.lower():
            try:
                return self._call_groq_direct(formatted_messages, temp, tokens, target_model, start_time)
            except Exception as e:
                # If direct groq fails, continue to litellm fallback
                pass

        _patch_litellm_compat()
        import litellm

        try:
            response = litellm.completion(
                model=target_model,
                messages=formatted_messages,
                temperature=temp,
                max_tokens=tokens,
                timeout=self.timeout_seconds,
                num_retries=self.num_retries,
            )
            latency = (time.time() - start_time) * 1000.0

            choice = response.choices[0]
            content = choice.message.content or ""
            usage = getattr(response, "usage", None)
            self._log_usage(target_model, usage, latency)

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
        start_time = time.time()
        target_model = model_override or self.default_model
        temp = temperature if temperature is not None else self.default_temperature
        tokens = max_tokens if max_tokens is not None else self.default_max_tokens

        formatted_messages = [{"role": m.role, "content": m.content} for m in messages]

        # Use native Groq client if Groq model requested
        if target_model.startswith("groq/") or "groq" in target_model.lower():
            try:
                return await self._call_groq_direct_async(formatted_messages, temp, tokens, target_model, start_time)
            except Exception as e:
                pass

        _patch_litellm_compat()
        import litellm

        try:
            response = await litellm.acompletion(
                model=target_model,
                messages=formatted_messages,
                temperature=temp,
                max_tokens=tokens,
                timeout=self.timeout_seconds,
                num_retries=self.num_retries,
            )
            latency = (time.time() - start_time) * 1000.0
            choice = response.choices[0]
            content = choice.message.content or ""
            usage = getattr(response, "usage", None)
            self._log_usage(target_model, usage, latency)

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

    @staticmethod
    def _log_usage(model: str, usage: Any, latency_ms: float) -> None:
        """Token counts per call, so LLM cost is visible in the logs."""
        Tracer.log_llm_call(
            model=model,
            prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
            completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
            duration_ms=latency_ms,
        )

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "provider": "litellm",
            "model": self.default_model,
            "temperature": self.default_temperature,
            "max_tokens": self.default_max_tokens,
            "timeout_seconds": self.timeout_seconds,
            "num_retries": self.num_retries,
        }
