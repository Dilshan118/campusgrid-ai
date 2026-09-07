"""
Backwards compatibility shim for CampusMicrogridOptimizer.
Delegates to src.agents.dispatch_explanation.milp_solver.
"""

from src.agents.dispatch_explanation.milp_solver import CampusMicrogridOptimizer

__all__ = ["CampusMicrogridOptimizer"]
