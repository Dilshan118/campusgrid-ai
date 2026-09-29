"""
CampusGrid AI: Agent 4 — Dispatch and Explanation (LLM · Optimization)
Formulates 48-period MILP cost minimization, eliminates peak demand spikes,
and synthesizes plain-English XAI justifications grounded in verified solver logs and tariff citations.
"""

import logging
from typing import Dict, Any, List, Optional
from src.agents.base.agent import BaseAgent
from src.domain.entities.optimization import OptimizationInput
from src.domain.interfaces.llm import LLMProvider
from src.domain.interfaces.optimizer import (
    MicrogridOptimizerInterface,
    XAIExplainerInterface,
    FaithfulnessVerifierInterface,
)
from src.agents.dispatch_explanation.milp_solver import CampusMicrogridOptimizer
from src.agents.dispatch_explanation.xai_explainer import (
    XAIExplainer,
    solver_only_explanation,
    tariff_text,
    comfort_verdict_text,
)
from src.agents.dispatch_explanation.faithfulness import FaithfulnessVerifier
from src.shared.constants import (
    BATTERY_CAPACITY_DEFAULT_KWH,
    BATTERY_MAX_POWER_DEFAULT_KW,
    BATTERY_SOC_MIN_RATIO,
    BATTERY_SOC_MAX_RATIO,
    MAX_DEMAND_SURCHARGE_LKR_KVA,
)

logger = logging.getLogger("campusgrid.agents.dispatch")

# The site battery, overridden by the container from settings and per request by the dispatch form.
DEFAULT_BATTERY = {
    "battery_capacity_kwh": BATTERY_CAPACITY_DEFAULT_KWH,
    "max_charge_rate_kw": BATTERY_MAX_POWER_DEFAULT_KW,
    "max_discharge_rate_kw": BATTERY_MAX_POWER_DEFAULT_KW,
    "initial_soc_ratio": 0.50,
    "min_soc_ratio": BATTERY_SOC_MIN_RATIO,
    "max_soc_ratio": BATTERY_SOC_MAX_RATIO,
}
# Fields a caller (the dispatch form) may override per request.
_REQUEST_BATTERY_FIELDS = ("battery_capacity_kwh", "max_charge_rate_kw", "max_discharge_rate_kw", "initial_soc_ratio")


class DispatchExplanationAgent(BaseAgent):
    """Agent 4: Solves microgrid dispatch and explains actions to operators."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        optimizer: Optional[MicrogridOptimizerInterface] = None,
        explainer: Optional[XAIExplainerInterface] = None,
        verifier: Optional[FaithfulnessVerifierInterface] = None,
        battery_defaults: Optional[Dict[str, float]] = None,
    ):
        super().__init__(
            name="Agent 4: Dispatch & Explanation",
            description="Solves 48-period MILP dispatch and generates plain-English XAI justifications."
        )
        self.optimizer = optimizer or CampusMicrogridOptimizer()
        self.explainer = explainer or XAIExplainer(llm_provider=llm_provider)
        self.verifier = verifier or FaithfulnessVerifier(llm_provider=llm_provider)
        self.battery_defaults = {**DEFAULT_BATTERY, **(battery_defaults or {})}

    def _battery_parameters(self, input_data: Dict[str, Any]) -> Dict[str, float]:
        params = dict(self.battery_defaults)
        for key in _REQUEST_BATTERY_FIELDS:
            if input_data.get(key) is not None:
                params[key] = float(input_data[key])
        return params

    def _run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        time_slots = input_data.get("time_slots", [])
        base_load = input_data.get("forecast_demand_kw", [])
        solar_gen = input_data.get("forecast_solar_kw", [])
        tariffs = input_data.get("tariffs_lkr_kwh", [])
        citations = input_data.get("citations", [])
        user_query = input_data.get("user_query", "Optimize 24h battery schedule to minimize peak demand charge.")
        comfort_feasible = input_data.get("feasibility_verdict")
        tariff_summary = input_data.get("tariff_summary")
        demand_charge = input_data.get("max_demand_penalty_lkr_kva")
        battery = self._battery_parameters(input_data)

        # Default tariffs if missing
        if not tariffs:
            tariffs = [30.0] * len(time_slots)

        opt_input = OptimizationInput(
            time_slots=time_slots,
            base_load_kw=base_load,
            solar_gen_kw=solar_gen,
            grid_tariff_lkr_kwh=tariffs,
            peak_demand_penalty_lkr_kva=float(demand_charge) if demand_charge is not None else MAX_DEMAND_SURCHARGE_LKR_KVA,
            **battery,
        )

        # 1. Solve MILP Optimization
        solver_output = self.optimizer.solve(opt_input)

        # 2. Synthesize Grounded XAI Justification. A language-model outage must not discard a
        #    solved plan: fall back to a deterministic explanation built from the solver numbers.
        try:
            explanation = self.explainer.generate_explanation(
                solver_output=solver_output,
                citations=citations,
                user_query=user_query,
                tariff_summary=tariff_summary,
                comfort_feasible=comfort_feasible,
            )
            explanation_source = "llm"
        except Exception as exc:
            logger.warning("Explanation model unavailable (%s); using the solver-only explanation.", type(exc).__name__)
            explanation = solver_only_explanation(solver_output, comfort_feasible)
            explanation_source = "solver_template"

        # 3. Verify Faithfulness against the solver, the citations and every other verified input
        audit_res = self.verifier.verify(
            explanation_text=explanation,
            solver_output=solver_output,
            citations=citations,
            grounding_text=self._grounding_text(user_query, tariff_summary, comfort_feasible, battery),
        )

        return {
            "solver_output": solver_output.model_dump(),
            "explanation": explanation,
            "explanation_source": explanation_source,
            "faithfulness_audit": audit_res,
            "baseline_cost_lkr": solver_output.baseline_cost_lkr,
            "optimized_cost_lkr": solver_output.optimized_cost_lkr,
            "net_savings_lkr": solver_output.net_savings_lkr,
            "savings_percentage": solver_output.savings_percentage,
            "peak_shaved_kw": round(solver_output.peak_demand_baseline_kw - solver_output.peak_demand_optimized_kw, 1),
            "battery_parameters": {**battery, "peak_demand_penalty_lkr_kva": opt_input.peak_demand_penalty_lkr_kva},
            "requires_human_approval": True,
            "citations": citations
        }

    @staticmethod
    def _grounding_text(
        user_query: str,
        tariff_summary: Optional[Dict[str, Any]],
        comfort_feasible: Optional[bool],
        battery: Dict[str, float],
    ) -> str:
        """Verified context an explanation may quote, besides the solver output and the citations."""
        return "\n".join([
            f"Operator request: {user_query}",
            f"Retrieved tariff:\n{tariff_text(tariff_summary)}",
            f"Comfort verdict: {comfort_verdict_text(comfort_feasible)}",
            (
                f"Battery: capacity {battery['battery_capacity_kwh']:g} kWh, charge limit {battery['max_charge_rate_kw']:g} kW, "
                f"discharge limit {battery['max_discharge_rate_kw']:g} kW, state-of-charge band "
                f"{battery['min_soc_ratio'] * 100:g}% to {battery['max_soc_ratio'] * 100:g}%, "
                f"starting at {battery['initial_soc_ratio'] * 100:g}%."
            ),
        ])
