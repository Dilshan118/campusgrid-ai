"""
CampusGrid AI: Prompt-Injection Pattern Detection
Deterministic patterns for instruction-like text. Used to quarantine ingested policy clauses
and to flag (not execute) instruction-like operator queries. Detection never grants anything:
the pipeline's safety comes from the solver and guardrails, these flags make attempts visible.
"""

import re
from typing import List

_INJECTION_PATTERNS = {
    "instruction_override": r"\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|earlier)\s+(?:instructions|rules|prompts|messages)",
    "rules_cancellation": r"(?:all\s+)?previous\s+rules\s+are\s+(?:cancelled|canceled|void|revoked)",
    "persona_hijack": r"\byou\s+are\s+now\b|\bact\s+as\s+(?:an?\s+)?(?:unrestricted|unregulated|jailbroken|dan)\b|\bUNREGULATED_\w+",
    "system_prompt_probe": r"\bsystem\s+prompt\b|\bend\s+of\s+system\s+instructions\b",
    "safety_override": r"\boverride\s+(?:all\s+)?safety\b|\bdisable\s+(?:all\s+)?(?:safety|guardrails?|protection)\b",
    "markup_injection": r"<\s*/?\s*(?:script|iframe|img|svg)\b|!\[[^\]]*\]\(\s*https?://",
    "secret_probe": r"\b(?:api[_\s-]?keys?|secret[_\s-]?keys?|credentials?|passwords?)\b",
    "fake_dialogue_turn": r"(?:^|\n)\s*(?:assistant|system)\s*:",
    "hardware_write": r"\b(?:modbus|bacnet)\b.*\b(?:write|register)\b|\bwrite\s+0x[0-9a-f]+",
}
_COMPILED = {name: re.compile(p, re.IGNORECASE) for name, p in _INJECTION_PATTERNS.items()}


def detect_prompt_injection(text: str) -> List[str]:
    """Returns the names of every injection pattern present in `text` (empty list if none)."""
    if not text:
        return []
    return [name for name, pattern in _COMPILED.items() if pattern.search(text)]
