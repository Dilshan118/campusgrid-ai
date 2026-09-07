"""
CampusGrid AI: Abstract LLM Provider Interface
Defines the contract for all LLM providers (LiteLLM, OpenAI, Gemini, Claude, Groq, Ollama, Mocks).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Type, TypeVar, AsyncIterator
from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)

class LLMMessage(BaseModel):
    role: str = Field(..., description="'system', 'user', or 'assistant'")
    content: str

class LLMResponse(BaseModel):
    content: str
    model: str
    provider: str
    tokens_prompt: Optional[int] = None
    tokens_completion: Optional[int] = None
    total_tokens: Optional[int] = None
    latency_ms: Optional[float] = None
    finish_reason: Optional[str] = None

class LLMProvider(ABC):
    """Abstract interface for large language model operations."""

    @abstractmethod
    def generate(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model_override: Optional[str] = None
    ) -> LLMResponse:
        """Executes synchronous chat completion."""
        pass

    @abstractmethod
    async def generate_async(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model_override: Optional[str] = None
    ) -> LLMResponse:
        """Executes asynchronous chat completion."""
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Returns metadata about the active provider and model."""
        pass
