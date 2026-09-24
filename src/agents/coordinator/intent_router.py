"""
CampusGrid AI: LLM Intent Router
Lets the language model decide which agents a query needs when the deterministic rules are
unsure. The model may only choose a label from a closed list; it never supplies a room, date,
temperature or any other value — those always come from the deterministic entity extractor.
"""

import json
import re
from typing import Optional, Tuple
from src.domain.interfaces.llm import LLMProvider, LLMMessage
from src.prompts.manager import PromptManager, get_prompt_manager
from src.agents.coordinator.nlp_parser import ROUTABLE_ACTIONS, ACTION_OUT_OF_SCOPE

_LABEL_ALIASES = {"general_query": ACTION_OUT_OF_SCOPE, "unknown": ACTION_OUT_OF_SCOPE}


class LLMIntentRouter:
    """Classifies a query into one of ROUTABLE_ACTIONS; returns None when the model's answer is unusable."""

    def __init__(self, llm_provider: LLMProvider, prompt_manager: Optional[PromptManager] = None):
        self.llm = llm_provider
        self.prompt_manager = prompt_manager or get_prompt_manager()

    def route(self, query: str) -> Optional[Tuple[str, float]]:
        # Braces would break str.format templating; tags are escaped so the query cannot close the data block.
        safe_query = query.replace("{", "(").replace("}", ")").replace("<", "‹").replace(">", "›")[:2000]
        prompt = self.prompt_manager.render("agents/coordinator/intent_extraction.txt", user_query=safe_query)
        messages = [
            LLMMessage(role="system", content="You are an intent classification router. Return JSON with an action label only."),
            LLMMessage(role="user", content=prompt),
        ]
        try:
            response = self.llm.generate(messages, temperature=0.0, max_tokens=80)
            text = response.content.strip()
            match = re.search(r"\{.*\}", text, re.DOTALL)
            parsed = json.loads(match.group(0) if match else text)
        except Exception:
            return None

        action = str(parsed.get("action", "")).strip().lower()
        action = _LABEL_ALIASES.get(action, action)
        if action not in ROUTABLE_ACTIONS:
            return None
        try:
            confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.7))))
        except (TypeError, ValueError):
            confidence = 0.7
        return action, confidence
