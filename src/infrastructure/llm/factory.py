"""
CampusGrid AI: LLM Provider Factory
Resolves the active LLM provider from settings dynamically.

LLM_PROVIDER names the vendor and LLM_MODEL the LiteLLM model string ('<vendor>/<model>').
The two must agree: a mismatch (e.g. LLM_PROVIDER=openai with a gemini/ model) or an unknown
provider stops startup instead of silently calling a different vendor than the one configured.
"""

from src.domain.interfaces.llm import LLMProvider
from src.infrastructure.llm.mock_provider import MockLLMProvider
from src.infrastructure.llm.litellm_provider import LiteLLMProvider
from src.config.settings import LLMSettings

# Vendor names accepted in LLM_PROVIDER. 'litellm' means "any vendor, taken from LLM_MODEL".
VENDOR_PROVIDERS = ("gemini", "openai", "anthropic", "groq", "ollama")


def resolve_model(provider_name: str, model: str) -> str:
    """Returns the LiteLLM model string for this provider, or raises ValueError if they disagree."""
    if provider_name == "litellm":
        return model
    if provider_name not in VENDOR_PROVIDERS:
        raise ValueError(
            f"LLM_PROVIDER='{provider_name}' is not supported. "
            f"Use 'mock', 'litellm' or one of: {', '.join(VENDOR_PROVIDERS)}."
        )
    if "/" not in model:
        return f"{provider_name}/{model}"
    model_vendor = model.split("/", 1)[0].lower()
    if model_vendor != provider_name:
        raise ValueError(
            f"LLM_PROVIDER='{provider_name}' but LLM_MODEL='{model}' belongs to '{model_vendor}'. "
            "Make them agree, or set LLM_PROVIDER=litellm to route by LLM_MODEL alone."
        )
    return model


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
            model=resolve_model(provider_name, settings.model),
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            api_keys=api_keys,
            timeout_seconds=settings.timeout_seconds,
            num_retries=settings.num_retries,
        )
