"""
Unit tests for LLM Provider abstraction and MockLLMProvider.
"""

import json

from src.infrastructure.llm.mock_provider import MockLLMProvider
from src.domain.interfaces.llm import LLMMessage
from src.agents.coordinator.nlp_parser import ROUTABLE_ACTIONS

def test_mock_llm_default_generation():
    provider = MockLLMProvider()
    messages = [
        LLMMessage(role="system", content="You are a helper."),
        LLMMessage(role="user", content="Hello")
    ]
    response = provider.generate(messages)

    assert response.provider == "mock"
    assert "CampusGrid AI" in response.content
    assert response.total_tokens is not None
    assert response.latency_ms is not None

def test_mock_llm_intent_extraction_abstains():
    # The mock cannot classify free text, so it answers with valid JSON whose label is outside
    # the router's allow-list; the router then keeps the deterministic rule-based intent.
    provider = MockLLMProvider()
    messages = [
        LLMMessage(role="system", content="Extract intent from user query."),
        LLMMessage(role="user", content="Optimize battery schedule for tomorrow.")
    ]
    response = provider.generate(messages)
    assert json.loads(response.content)["action"] not in ROUTABLE_ACTIONS

def test_mock_llm_custom_override():
    provider = MockLLMProvider(default_response="Custom test response")
    messages = [LLMMessage(role="user", content="test")]
    response = provider.generate(messages)
    assert response.content == "Custom test response"
