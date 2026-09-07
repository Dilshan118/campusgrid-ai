"""
CampusGrid AI: Agent 4 — Dispatch and Explanation (LLM · Optimization)
Formulates 48-period MILP cost minimization, eliminates peak demand spikes,
and synthesizes plain-English XAI justifications grounded in verified solver logs and tariff citations.
"""

from typing import Dict, Any, List, Optional
from src.agents.base.agent import BaseAgent
from src.agents.dispatch_explanation.milp_solver import CampusMicrogridOptimizer
from src.agents.dispatch_explanation.xai_explainer import XAIExplainer
from src.agents.dispatch_explanation.faithfulness import FaithfulnessVerifier
from src.domain.entities.optimization import OptimizationInput
from src.domain.interfaces.llm import LLMProvider

class DispatchExplanationAgent(BaseAgent):
    """Agent 4: Solves microgrid dispatch and explains actions to operators."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        optimizer: Optional[CampusMicrogridOptimizer] = None,
        explainer: Optional[XAIExplainer] = None,
        verifier: Optional[FaithfulnessVerifier] = None
    ):
        super().__init__(
            name="Agent 4: Dispatch & Explanation",
            description="Solves 48-period MILP dispatch and generates plain-English XAI justifications."
        )
        self.optimizer = optimizer or CampusMicrogridOptimizer()
        self.explainer = explainer or XAIExplainer(llm_provider=llm_provider)
        self.verifier = verifier or FaithfulnessVerifier(llm_provider=llm_provider)

    def _run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        time_slots = input_data.get("time_slots", [])
        base_load = input_data.get("forecast_demand_kw", [])
        solar_gen = input_data.get("forecast_solar_kw", [])
        tariffs = input_data.get("tariffs_lkr_kwh", [])
        citations = input_data.get("citations", [])
        user_query = input_data.get("user_query", "Optimize 24h battery schedule to minimize peak demand charge.")

        # Default tariffs if missing
        if not tariffs:
            tariffs = [30.0] * len(time_slots)

        opt_input = OptimizationInput(
            time_slots=time_slots,
            base_load_kw=base_load,
            solar_gen_kw=solar_gen,
            grid_tariff_lkr_kwh=tariffs
        )

        # 1. Solve MILP Optimization
        solver_output = self.optimizer.solve(opt_input)

        # 2. Synthesize Grounded XAI Justification
        explanation = self.explainer.generate_explanation(
            solver_output=solver_output,
            citations=citations,
            user_query=user_query
        )

        # 3. Verify Faithfulness
        audit_res = self.verifier.verify(
            explanation_text=explanation,
            solver_output=solver_output
        )

        return {
            "solver_output": solver_output.model_dump(),
            "explanation": explanation,
            "faithfulness_audit": audit_res,
            "baseline_cost_lkr": solver_output.baseline_cost_lkr,
            "optimized_cost_lkr": solver_output.optimized_cost_lkr,
            "net_savings_lkr": solver_output.net_savings_lkr,
            "savings_percentage": solver_output.savings_percentage,
            "peak_shaved_kw": solver_output.peak_demand_baseline_kw - solver_output.peak_demand_optimized_kw,
            "requires_human_approval": True,
            "citations": citations
        }
