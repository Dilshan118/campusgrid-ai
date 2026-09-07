"""
CampusGrid AI: Optimize Dispatch Schedule Use Case
Executes mathematical cost minimization (MILP) to eliminate peak demand surcharges.
"""

from typing import Dict, Any, List, Optional
from src.agents.dispatch_explanation.milp_solver import CampusMicrogridOptimizer
from src.domain.entities.optimization import OptimizationInput, OptimizationResult

class OptimizeDispatchScheduleUseCase:
    """Executes 48-period MILP cost minimization."""

    def __init__(self, optimizer: Optional[CampusMicrogridOptimizer] = None):
        self.optimizer = optimizer or CampusMicrogridOptimizer()

    def execute(
        self,
        time_slots: List[str],
        base_load_kw: List[float],
        solar_gen_kw: List[float],
        grid_tariff_lkr_kwh: List[float],
        battery_capacity_kwh: float = 500.0,
        max_charge_rate_kw: float = 100.0,
        max_discharge_rate_kw: float = 100.0
    ) -> OptimizationResult:
        opt_input = OptimizationInput(
            time_slots=time_slots,
            base_load_kw=base_load_kw,
            solar_gen_kw=solar_gen_kw,
            grid_tariff_lkr_kwh=grid_tariff_lkr_kwh,
            battery_capacity_kwh=battery_capacity_kwh,
            max_charge_rate_kw=max_charge_rate_kw,
            max_discharge_rate_kw=max_discharge_rate_kw
        )
        return self.optimizer.solve(opt_input)
