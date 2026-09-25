"""
CampusGrid AI: Microgrid Dispatch Optimization & Explainable AI (XAI) Interfaces
Assigned to: Member 4 (Operations Research, Linear Optimization & Responsible AI)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from src.domain.entities.optimization import OptimizationInput, OptimizationResult

class MicrogridOptimizerInterface(ABC):
    """Abstract interface for deterministic microgrid linear / MILP optimization solvers."""

    @abstractmethod
    def solve(self, opt_input: OptimizationInput) -> OptimizationResult:
        """
        Formulates and solves 48-interval microgrid energy cost and peak demand optimization.
        Enforces battery electrochemical SOC bounds (20% - 90%) and power balance constraints.
        """
        pass


class XAIExplainerInterface(ABC):
    """Abstract interface for explainable AI justification synthesizers."""

    @abstractmethod
    def generate_explanation(
        self,
        solver_output: OptimizationResult,
        citations: List[Dict[str, Any]],
        user_query: str,
        tariff_summary: Optional[Dict[str, Any]] = None,
        comfort_feasible: Optional[bool] = None,
    ) -> str:
        """
        Translates numerical solver results and retrieved regulatory citations
        into plain-English operator justifications. `tariff_summary` carries the rates Agent 3
        retrieved; `comfort_feasible` is Agent 2's verdict (None when unknown).
        """
        pass


class FaithfulnessVerifierInterface(ABC):
    """Abstract interface for automated faithfulness and hallucination auditing."""

    @abstractmethod
    def verify(
        self,
        explanation_text: str,
        solver_output: OptimizationResult,
        citations: Optional[List[Dict[str, Any]]] = None,
        grounding_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Audits generated claims against ground-truth solver figures, the retrieved citations and
        any other verified context (`grounding_text`), and returns a verification report.
        Must fail closed: a check that cannot be completed reports is_faithful=False."""
        pass
