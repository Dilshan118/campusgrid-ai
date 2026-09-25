"""
CampusGrid AI: Mock LLM Provider
Deterministic, zero-cost LLM provider for fast unit tests and offline execution.
Generates structured intents, grounded XAI justifications, and fact-check responses.
"""

import time
import json
import re
from typing import List, Dict, Any, Optional
from src.domain.interfaces.llm import LLMProvider, LLMMessage, LLMResponse

# Figures the XAI prompt lists in its "Verified Mathematical Solver Log"; the mock explanation
# quotes them back, so offline plans pass the deterministic number check honestly.
_SOLVER_LOG_PATTERNS = {
    "baseline": r"Baseline Cost: LKR (-?[\d,]+\.\d+)",
    "optimized": r"Optimized Cost: LKR (-?[\d,]+\.\d+)",
    "savings": r"Net Savings: LKR (-?[\d,]+\.\d+) \((-?[\d.]+)%\)",
    "peak": r"Peak Grid Demand: ([\d.]+) kW -> ([\d.]+) kW",
    "discharge": r"Maximum Battery Discharge: ([\d.]+) kW",
}


def _grounded_mock_explanation(prompt: str) -> Optional[str]:
    found = {k: re.search(p, prompt) for k, p in _SOLVER_LOG_PATTERNS.items()}
    if not all(found.values()):
        return None
    comfort = (
        "The digital twin confirms the room stays within the ASHRAE-55 comfort band."
        if "Comfort maintained" in prompt
        else "The digital twin did not confirm the comfort band, so review the comfort warning before approving."
    )
    return (
        f"Based on the MILP solver's plan, the battery discharges at up to {found['discharge'].group(1)} kW, "
        f"lowering the peak grid demand from {found['peak'].group(1)} kW to {found['peak'].group(2)} kW. "
        f"The daily cost falls from LKR {found['baseline'].group(1)} to LKR {found['optimized'].group(1)}, "
        f"a saving of LKR {found['savings'].group(1)} ({found['savings'].group(2)}%). {comfort}"
    )

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
        # 2. Intent extraction prompt. The mock cannot read free text, so it abstains with a label
        #    outside the router's allow-list; the router then returns None and the deterministic
        #    rules decide. (Always answering "optimize_dispatch" turned every unclear or off-topic
        #    query into a pending dispatch plan.)
        elif "intent" in system_instruction.lower():
            content = json.dumps({
                "action": "abstain",
                "confidence": 0.0,
                "reasoning": "Mock provider does not classify free text; the rule-based intent stands."
            })
        # 3. Faithfulness check prompt. The mock does not read the text it is asked to audit, and
        #    says so; the verifier's deterministic number check is what decides offline.
        elif any(w in system_instruction.lower() for w in ("faithfulness", "verify", "auditor")):
            content = json.dumps({
                "is_faithful": True,
                "hallucinated_claims": [],
                "confidence": 1.0,
                "reasoning": "Mock provider does not audit text; the deterministic number check decides."
            })
        # 4. Agent 1 forecast briefing note (summarisation)
        elif "briefing note" in system_instruction.lower():
            content = (
                "Tomorrow's demand follows the usual weekday lecture pattern with an afternoon peak. "
                "Flagged intervals coincide with the hottest hours of the day."
            )
        # 5. XAI justification prompt: quote the solver figures the prompt provides
        elif _grounded_mock_explanation(last_user_message):
            content = _grounded_mock_explanation(last_user_message)
        # 6. Anything else: a fixed sample justification
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
