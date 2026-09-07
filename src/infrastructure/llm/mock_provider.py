"""
CampusGrid AI: Mock LLM Provider
Deterministic, zero-cost LLM provider for fast unit tests and offline execution.
Generates structured intents, grounded XAI justifications, and fact-check responses.
"""

import time
import json
from typing import List, Dict, Any, Optional
from src.domain.interfaces.llm import LLMProvider, LLMMessage, LLMResponse

class MockLLMProvider(LLMProvider):
    """Deterministic LLM Provider that synthesizes domain-grounded responses without network calls."""

    def __init__(self, default_response: Optional[str] = None):
        self.default_response = default_response
        self.call_history: List[List[LLMMessage]] = []

    def generate(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model_override: Optional[str] = None
    ) -> LLMResponse:
        start_time = time.time()
        self.call_history.append(messages)

        last_user_message = ""
        system_instruction = ""
        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            elif msg.role == "user":
                last_user_message = msg.content

        # 1. Check if an explicit response override was configured
        if self.default_response:
            content = self.default_response
        # 2. Intent extraction prompt
        elif "intent" in system_instruction.lower() or "action" in system_instruction.lower():
            content = json.dumps({
                "action": "optimize_dispatch",
                "target": "campus_chillers",
                "building": "Main Academic Complex",
                "room": "Lecture Hall 1",
                "date": "2026-09-06",
                "target_temp_c": 23.5,
                "confidence": 0.95
            })
        # 3. Faithfulness check prompt
        elif "faithfulness" in system_instruction.lower() or "verify" in system_instruction.lower():
            content = json.dumps({
                "is_faithful": True,
                "hallucinated_claims": [],
                "confidence": 1.0,
                "reasoning": "All stated kilowatt values and tariff rates match mathematical solver output."
            })
        # 4. Standard XAI Plain-English Justification
        else:
            content = (
                "Based on the mathematical optimization (MILP solver), CampusGrid AI successfully scheduled "
                "the 500 kWh battery storage to discharge 100 kW during the expensive evening peak period "
                "(18:00 - 22:30, PUCSL GP-2 peak tariff: LKR 58.00/kWh). "
                "This shaved the 15-minute maximum demand spike from 820.0 kW down to 720.0 kW, "
                "yielding a net daily cost reduction of LKR 43,500 (approx. 14.8% savings). "
                "Precooling in Lecture Hall 1 maintained indoor comfort strictly within ASHRAE-55 standards (21.0°C - 25.5°C)."
            )

        latency = (time.time() - start_time) * 1000.0
        return LLMResponse(
            content=content,
            model=model_override or "mock/campusgrid-deterministic",
            provider="mock",
            tokens_prompt=len(last_user_message.split()) * 2,
            tokens_completion=len(content.split()) * 2,
            total_tokens=(len(last_user_message.split()) + len(content.split())) * 2,
            latency_ms=latency,
            finish_reason="stop"
        )

    async def generate_async(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model_override: Optional[str] = None
    ) -> LLMResponse:
        return self.generate(messages, temperature, max_tokens, model_override)

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "provider": "mock",
            "model": "mock/campusgrid-deterministic",
            "is_local": True
        }
