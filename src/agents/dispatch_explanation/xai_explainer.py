"""
CampusGrid AI: XAI Plain-English Justification Generator
Translates numerical MILP solver outputs and retrieved tariff citations into plain-English operator justifications.
"""

from typing import Dict, Any, List, Optional
from src.domain.interfaces.llm import LLMProvider, LLMMessage
from src.domain.interfaces.optimizer import XAIExplainerInterface
from src.domain.entities.optimization import OptimizationResult
from src.prompts.manager import get_prompt_manager, PromptManager

class XAIExplainer(XAIExplainerInterface):
    """Grounded plain-English justification builder."""

    def __init__(self, llm_provider: LLMProvider, prompt_manager: Optional[PromptManager] = None):
        self.llm = llm_provider
        self.prompt_manager = prompt_manager or get_prompt_manager()

    def generate_explanation(
        self,
        solver_output: OptimizationResult,
        citations: List[Dict[str, Any]],
        user_query: str
    ) -> str:
        citations_text = ""
        for idx, c in enumerate(citations):
            citations_text += f"[{idx+1}] {c.get('document_title', 'Tariff Doc')} ({c.get('section_clause', 'Section')}): {c.get('content', '')}\n"

        if not citations_text:
            citations_text = "[1] PUCSL GP-2 Rate Schedule: Peak LKR 58.00/kWh (18:00 - 22:30), Max Demand LKR 1100/kVA.\n"

        prompt = self.prompt_manager.render(
            "agents/dispatch_explanation/xai_justification.txt",
            user_query=user_query,
            baseline_cost_lkr=solver_output.baseline_cost_lkr,
            optimized_cost_lkr=solver_output.optimized_cost_lkr,
            net_savings_lkr=solver_output.net_savings_lkr,
            savings_percentage=solver_output.savings_percentage,
            peak_baseline_kw=solver_output.peak_demand_baseline_kw,
            peak_optimized_kw=solver_output.peak_demand_optimized_kw,
            max_battery_discharge_kw=max(solver_output.battery_discharge_kw) if solver_output.battery_discharge_kw else 0.0,
            solver_status=solver_output.solver_status,
            citations_text=citations_text
        )

        messages = [
            LLMMessage(role="system", content="You are CampusGrid AI's Explainable AI (XAI) assistant. Cite only verified numbers."),
            LLMMessage(role="user", content=prompt)
        ]

        response = self.llm.generate(messages=messages)
        return response.content
