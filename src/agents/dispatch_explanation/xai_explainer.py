"""
CampusGrid AI: XAI Plain-English Justification Generator
Translates numerical MILP solver outputs and retrieved tariff citations into plain-English operator justifications.

Every figure the model is given comes from the solver, Agent 3's retrieved tariff or Agent 2's
comfort verdict — the prompt carries no hard-coded rates or comfort claims of its own.
"""

from typing import Dict, Any, List, Optional
from src.domain.interfaces.llm import LLMProvider, LLMMessage
from src.domain.interfaces.optimizer import XAIExplainerInterface
from src.domain.entities.optimization import OptimizationResult
from src.prompts.manager import get_prompt_manager, PromptManager

# Enough of each clause for the model to cite it; the full text is already in the plan's citations.
CITATION_PROMPT_CHARS = 300

_RATE_LABELS = (("peak", "Peak"), ("day", "Day"), ("off_peak", "Off-peak"))


def comfort_verdict_text(comfort_feasible: Optional[bool]) -> str:
    if comfort_feasible is True:
        return "Comfort maintained: the simulated room stays within the ASHRAE-55 comfort band."
    if comfort_feasible is False:
        return ("Comfort NOT confirmed: the digital twin predicts, or could not rule out, "
                "temperatures outside the ASHRAE-55 comfort band.")
    return "Unknown: no comfort verdict was provided."


def tariff_text(tariff_summary: Optional[Dict[str, Any]]) -> str:
    if not tariff_summary:
        return "Not provided."
    rates = tariff_summary.get("rates_lkr_kwh") or {}
    windows = tariff_summary.get("windows") or {}
    lines = []
    for key, label in _RATE_LABELS:
        if rates.get(key) is not None:
            window = f" ({windows[key]})" if windows.get(key) else ""
            lines.append(f"- {label}: LKR {float(rates[key]):,.2f}/kWh{window}")
    if tariff_summary.get("max_demand_penalty_lkr_kva") is not None:
        lines.append(f"- Maximum demand charge: LKR {float(tariff_summary['max_demand_penalty_lkr_kva']):,.2f}/kVA per month")
    return "\n".join(lines) or "Not provided."


def solver_only_explanation(solver_output: OptimizationResult, comfort_feasible: Optional[bool] = None) -> str:
    """Deterministic explanation built only from solver figures, used when the language model is unavailable."""
    s = solver_output
    if s.net_savings_lkr >= 0:
        outcome = f"saving LKR {s.net_savings_lkr:,.2f} ({s.savings_percentage:.1f}%)"
    else:
        outcome = f"costing LKR {abs(s.net_savings_lkr):,.2f} more ({s.savings_percentage:.1f}%)"
    return (
        f"The MILP solver's battery schedule changes the peak grid demand from {s.peak_demand_baseline_kw:.1f} kW "
        f"to {s.peak_demand_optimized_kw:.1f} kW and the daily cost from LKR {s.baseline_cost_lkr:,.2f} to "
        f"LKR {s.optimized_cost_lkr:,.2f}, {outcome}. {comfort_verdict_text(comfort_feasible)} "
        "This summary was generated from the solver output because the language model was unavailable."
    )


class XAIExplainer(XAIExplainerInterface):
    """Grounded plain-English justification builder."""

    def __init__(self, llm_provider: LLMProvider, prompt_manager: Optional[PromptManager] = None):
        self.llm = llm_provider
        self.prompt_manager = prompt_manager or get_prompt_manager()

    def generate_explanation(
        self,
        solver_output: OptimizationResult,
        citations: List[Dict[str, Any]],
        user_query: str,
        tariff_summary: Optional[Dict[str, Any]] = None,
        comfort_feasible: Optional[bool] = None,
    ) -> str:
        citations_text = ""
        for idx, c in enumerate(citations):
            content = str(c.get("content", ""))
            if len(content) > CITATION_PROMPT_CHARS:
                content = content[:CITATION_PROMPT_CHARS].rstrip() + "…"
            citations_text += f"[{idx+1}] {c.get('document_title', 'Tariff Doc')} ({c.get('section_clause', 'Section')}): {content}\n"

        if not citations_text:
            citations_text = "None retrieved.\n"

        if solver_output.energy_savings_lkr is not None and solver_output.demand_charge_savings_lkr is not None:
            savings_breakdown = (
                f"  - from energy prices: LKR {solver_output.energy_savings_lkr:,.2f}\n"
                f"  - from a lower peak (daily share of the demand charge): LKR {solver_output.demand_charge_savings_lkr:,.2f}"
            )
        else:
            savings_breakdown = "  - (energy / demand-charge breakdown not reported by this solver)"

        prompt = self.prompt_manager.render(
            "agents/dispatch_explanation/xai_justification.txt",
            user_query=user_query,
            baseline_cost_lkr=solver_output.baseline_cost_lkr,
            optimized_cost_lkr=solver_output.optimized_cost_lkr,
            net_savings_lkr=solver_output.net_savings_lkr,
            savings_percentage=solver_output.savings_percentage,
            savings_breakdown=savings_breakdown,
            peak_baseline_kw=solver_output.peak_demand_baseline_kw,
            peak_optimized_kw=solver_output.peak_demand_optimized_kw,
            max_battery_discharge_kw=max(solver_output.battery_discharge_kw) if solver_output.battery_discharge_kw else 0.0,
            solver_status=solver_output.solver_status,
            tariff_text=tariff_text(tariff_summary),
            comfort_text=comfort_verdict_text(comfort_feasible),
            citations_text=citations_text
        )

        messages = [
            LLMMessage(role="system", content="You are CampusGrid AI's Explainable AI (XAI) assistant. Cite only verified numbers."),
            LLMMessage(role="user", content=prompt)
        ]

        response = self.llm.generate(messages=messages)
        return response.content
