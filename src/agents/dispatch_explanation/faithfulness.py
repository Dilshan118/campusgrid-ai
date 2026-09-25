"""
CampusGrid AI: Automated Faithfulness & Fact-Checking Verifier
Ensures LLM output quotes strictly verified solver figures and tariff rules.

Two checks, both required to pass (fail closed):
1. Deterministic number check — every figure and clock time in the explanation must appear in
   the solver output, the retrieved citations, or the verified context passed in
   (`grounding_text`: the operator's query, the retrieved tariff, battery and comfort limits).
   This is the coursework rule "every numerical claim must match the solver log or a citation".
2. LLM audit — a second model call for claims that are not numbers. If its reply cannot be
   read, or the call fails, the explanation is reported as NOT verified.
"""

import json
import re
from typing import Dict, Any, List, Optional, Tuple
from src.domain.interfaces.llm import LLMProvider, LLMMessage
from src.domain.interfaces.optimizer import FaithfulnessVerifierInterface
from src.domain.entities.optimization import OptimizationResult
from src.prompts.manager import get_prompt_manager, PromptManager

# Figures in the explanation: "16,212.96", "4.3", "-120". Numbers glued to a word by a hyphen
# ("GP-2", "ASHRAE-55-2023") are identifiers, not quantities, and are not extracted.
_CLAIMED_NUMBER = re.compile(r"(?<![\w.\-])-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?!\d)(?![.,]\d)")
# Every digit sequence in trusted text, so a trusted "GP-2" or "55-2023" still grounds its numbers.
_TRUSTED_NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
_CLOCK_TIME = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_LIST_MARKER = re.compile(r"^\s*\d+[.)]\s+", re.MULTILINE)

# Structural numbers of the problem itself (matched exactly): 15-minute demand, 24-hour horizon,
# 30-minute slots, 48 intervals, and small counts ("1 battery", "2 clauses").
_STRUCTURAL_NUMBERS = {0.0, 1.0, 2.0, 15.0, 24.0, 30.0, 48.0}
_LARGE_FIGURE_REL_TOLERANCE = 0.005  # "LKR 16,200" for 16,212.96: whole numbers of 1,000 or more
_CITATION_PROMPT_CHARS = 300


def _to_float(token: str) -> float:
    return float(token.replace(",", ""))


def _normalise_time(hours: str, minutes: str) -> str:
    return f"{int(hours):02d}:{minutes}"


def _is_supported(token: str, allowed: List[float]) -> bool:
    """A figure is supported if it is a rounding of an allowed value at the precision it is written."""
    value = abs(_to_float(token))
    if value in _STRUCTURAL_NUMBERS:
        return True
    decimals = len(token.split(".", 1)[1]) if "." in token else 0
    tolerance = 0.5 * 10 ** (-decimals) + 1e-9
    for a in allowed:
        if abs(value - a) <= tolerance:
            return True
        if decimals == 0 and value >= 1000 and abs(value - a) <= _LARGE_FIGURE_REL_TOLERANCE * a:
            return True
    return False


def _solver_figures(solver: OptimizationResult) -> List[float]:
    figures = [
        solver.baseline_cost_lkr, solver.optimized_cost_lkr, solver.net_savings_lkr, solver.savings_percentage,
        solver.peak_demand_baseline_kw, solver.peak_demand_optimized_kw,
        solver.peak_demand_baseline_kw - solver.peak_demand_optimized_kw,
        solver.baseline_cost_lkr - solver.optimized_cost_lkr,
    ]
    figures += [v for v in (solver.energy_savings_lkr, solver.demand_charge_savings_lkr) if v is not None]
    for series in (solver.optimized_grid_kw, solver.battery_charge_kw, solver.battery_discharge_kw, solver.battery_soc_kwh):
        figures += series
    figures += [b.threshold for b in solver.binding_constraints] + [b.actual_value for b in solver.binding_constraints]
    return figures


def _trusted_text(citations: List[Dict[str, Any]], grounding_text: Optional[str]) -> str:
    parts = [grounding_text or ""]
    for c in citations:
        parts += [str(c.get("document_title", "")), str(c.get("section_clause", "")), str(c.get("content", ""))]
    return "\n".join(parts)


def check_numbers(
    explanation_text: str,
    solver: OptimizationResult,
    citations: Optional[List[Dict[str, Any]]] = None,
    grounding_text: Optional[str] = None,
) -> Tuple[List[str], int]:
    """Returns (unsupported figures as written in the text, number of figures checked)."""
    trusted = _trusted_text(citations or [], grounding_text)
    allowed = [abs(v) for v in _solver_figures(solver)]
    allowed += [_to_float(t) for t in _TRUSTED_NUMBER.findall(trusted)]
    allowed_times = {_normalise_time(h, m) for h, m in _CLOCK_TIME.findall(trusted)}

    text = _LIST_MARKER.sub("", explanation_text or "")
    unsupported: List[str] = []
    checked = 0

    for match in _CLOCK_TIME.finditer(text):
        checked += 1
        if _normalise_time(match.group(1), match.group(2)) not in allowed_times:
            unsupported.append(match.group(0))
    text = _CLOCK_TIME.sub(" ", text)

    for token in _CLAIMED_NUMBER.findall(text):
        checked += 1
        if not _is_supported(token, allowed):
            unsupported.append(token)
    return unsupported, checked


def _parse_verdict(reply: str) -> Optional[Dict[str, Any]]:
    """Reads the auditor's JSON even when wrapped in prose or ```json fences; None if unusable."""
    match = re.search(r"\{.*\}", reply or "", re.DOTALL)
    try:
        parsed = json.loads(match.group(0) if match else reply)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, dict) or not isinstance(parsed.get("is_faithful"), bool):
        return None
    return parsed


class FaithfulnessVerifier(FaithfulnessVerifierInterface):
    """Audits generated explanations for factual grounding."""

    def __init__(self, llm_provider: LLMProvider, prompt_manager: Optional[PromptManager] = None):
        self.llm = llm_provider
        self.prompt_manager = prompt_manager or get_prompt_manager()

    def verify(
        self,
        explanation_text: str,
        solver_output: OptimizationResult,
        citations: Optional[List[Dict[str, Any]]] = None,
        grounding_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        citations = citations or []
        unsupported, checked = check_numbers(explanation_text, solver_output, citations, grounding_text)
        numbers_ok = not unsupported

        verdict, model_error = self._model_verdict(explanation_text, solver_output, citations, grounding_text)
        model_ok = bool(verdict and verdict["is_faithful"])

        claims = [f"Unsupported figure: {u}" for u in unsupported]
        if verdict and not model_ok:
            claims += [str(c) for c in (verdict.get("hallucinated_claims") or [])]

        reasons = [
            f"Number check: {checked - len(unsupported)} of {checked} figures match the solver output, citations or verified context."
        ]
        if verdict is None:
            reasons.append(f"Model audit could not be completed ({model_error}); the explanation is treated as unverified.")
        else:
            reasons.append(f"Model audit: {verdict.get('reasoning') or ('passed' if model_ok else 'failed')}")

        try:
            confidence = float(verdict.get("confidence", 0.0)) if (verdict and numbers_ok) else 0.0
        except (TypeError, ValueError):
            confidence = 0.0

        return {
            "is_faithful": numbers_ok and model_ok,
            "hallucinated_claims": claims,
            "confidence": max(0.0, min(1.0, confidence)),
            "reasoning": " ".join(reasons),
            "checks": {
                "numbers": {"passed": numbers_ok, "figures_checked": checked, "unsupported": unsupported},
                "model": {"passed": model_ok if verdict is not None else None},
            },
        }

    def _model_verdict(
        self,
        explanation_text: str,
        solver_output: OptimizationResult,
        citations: List[Dict[str, Any]],
        grounding_text: Optional[str],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        reference = [grounding_text or "No additional context."]
        for c in citations:
            content = str(c.get("content", ""))[:_CITATION_PROMPT_CHARS]
            reference.append(f"- {c.get('document_title', '')} ({c.get('section_clause', '')}): {content}")
        prompt = self.prompt_manager.render(
            "agents/dispatch_explanation/faithfulness_check.txt",
            generated_text=explanation_text,
            baseline_cost_lkr=solver_output.baseline_cost_lkr,
            optimized_cost_lkr=solver_output.optimized_cost_lkr,
            net_savings_lkr=solver_output.net_savings_lkr,
            savings_percentage=solver_output.savings_percentage,
            peak_baseline_kw=solver_output.peak_demand_baseline_kw,
            peak_optimized_kw=solver_output.peak_demand_optimized_kw,
            reference_text="\n".join(reference),
        )
        messages = [
            LLMMessage(role="system", content="You are a strict factual auditor. Return valid JSON only."),
            LLMMessage(role="user", content=prompt)
        ]
        try:
            response = self.llm.generate(messages=messages, temperature=0.0)
        except Exception as exc:  # provider outage: fail closed, never "verified by default"
            return None, f"model call failed: {type(exc).__name__}"
        verdict = _parse_verdict(response.content)
        return verdict, (None if verdict else "reply was not a readable JSON verdict")
