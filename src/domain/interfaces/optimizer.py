"""
CampusGrid AI: Microgrid Dispatch Optimization & Explainable AI (XAI) Interfaces
Assigned to: Member 4 (Operations Research, Linear Optimization & Responsible AI)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
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
        user_query: str
    ) -> str:
        """
        Translates numerical solver results and retrieved regulatory citations
        into plain-English operator justifications.
        """
        pass


class FaithfulnessVerifierInterface(ABC):
    """Abstract interface for automated faithfulness and hallucination auditing."""

    @abstractmethod
    def verify(
        self,
        explanation_text: str,
        solver_output: OptimizationResult
    ) -> Dict[str, Any]:
        """Audits generated claims against ground-truth solver figures and returns a verification report."""
        pass
