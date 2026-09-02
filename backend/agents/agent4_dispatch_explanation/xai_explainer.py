"""
Agent 4 Workstream: Dispatch and Explanation (LLM · Optimization)
Uses the active LLM (via LiteLLM Manager) to translate numerical MILP solver logs
and retrieved PUCSL tariff citations into plain-English explanations.
"""

from typing import Dict, Any
from backend.core.llm_manager import get_llm

llm = get_llm()

class XAIExplainer:
    """
    Synthesizes grounded explanations for human facility managers.
    Enforces the Golden Safety Rule: receives verified solver numbers only,
    never raw high-frequency telemetry.
    """
    def generate_explanation(
        self,
        solver_output: Dict[str, Any],
        retrieved_citations: list,
        user_query: str
    ) -> str:
        """
        Calls the active LLM (Gemini, OpenAI, Claude, Groq, or Ollama)
        to produce a human-readable justification citing tariff clauses.
        """
        system_prompt = (
            "You are CampusGrid AI's Explainable AI (XAI) assistant. "
            "Explain microgrid dispatch actions in plain English. "
            "Quote only numbers verified in the solver log and cite official PUCSL clauses."
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Query: {user_query}\nSolver Output: {solver_output}\nCitations: {retrieved_citations}"}
        ]
        
        return llm.generate(messages=messages)
