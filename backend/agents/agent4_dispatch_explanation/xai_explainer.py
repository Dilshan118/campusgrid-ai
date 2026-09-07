"""
Backwards compatibility shim for XAIExplainer.
Delegates to src.agents.dispatch_explanation.xai_explainer.
"""

from typing import Dict, Any, List
from src.application.container import get_container
from src.agents.dispatch_explanation.xai_explainer import XAIExplainer as ModularXAIExplainer
from src.domain.entities.optimization import OptimizationResult

class XAIExplainer:
    def __init__(self):
        self.container = get_container()
        self._explainer = ModularXAIExplainer(llm_provider=self.container.llm_provider)

    def generate_explanation(
        self,
        solver_output: Any,
        retrieved_citations: list,
        user_query: str
    ) -> str:
        if isinstance(solver_output, dict):
            # Parse dict to OptimizationResult
            try:
                opt_res = OptimizationResult(**solver_output)
            except Exception:
                opt_res = OptimizationResult(
                    time_slots=[],
                    optimized_grid_kw=[],
                    battery_charge_kw=[],
                    battery_discharge_kw=[],
                    battery_soc_kwh=[],
                    baseline_cost_lkr=float(solver_output.get("baseline_cost_lkr", 0.0)),
                    optimized_cost_lkr=float(solver_output.get("optimized_cost_lkr", 0.0)),
                    net_savings_lkr=float(solver_output.get("net_savings_lkr", 0.0)),
                    savings_percentage=float(solver_output.get("savings_percentage", 0.0)),
                    peak_demand_baseline_kw=float(solver_output.get("peak_demand_baseline_kw", 0.0)),
                    peak_demand_optimized_kw=float(solver_output.get("peak_demand_optimized_kw", 0.0))
                )
        else:
            opt_res = solver_output

        return self._explainer.generate_explanation(
            solver_output=opt_res,
            citations=retrieved_citations,
            user_query=user_query
        )

__all__ = ["XAIExplainer"]
