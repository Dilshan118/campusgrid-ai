"""
Unit tests for deterministic Mixed-Integer Linear Programming (MILP) dispatch solver.
Validates both the reference baseline optimization and checks Member 4 implementation status.
"""

import pytest
from src.infrastructure.reference_baselines.baseline_milp import BaselineCampusMicrogridOptimizer
from src.agents.dispatch_explanation.milp_solver import CampusMicrogridOptimizer
from src.domain.entities.optimization import OptimizationInput

def test_reference_milp_solver_48_intervals():
    """Verify reference baseline PuLP optimization runs cleanly on 48 intervals."""
    optimizer = BaselineCampusMicrogridOptimizer(battery_cap_kwh=500.0, max_kw=100.0)

    slots = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]
    demands = [300.0 + (350.0 if 8 <= h <= 17 else 0.0) for h in range(24) for _ in (0, 30)]
    solars = [200.0 if 9 <= h <= 15 else 0.0 for h in range(24) for _ in (0, 30)]
    tariffs = [58.0 if 18 <= h < 23 else (15.0 if h < 6 else 30.0) for h in range(24) for _ in (0, 30)]

    opt_input = OptimizationInput(
        time_slots=slots,
        base_load_kw=demands,
        solar_gen_kw=solars,
        grid_tariff_lkr_kwh=tariffs,
        battery_capacity_kwh=500.0,
        max_charge_rate_kw=100.0,
        max_discharge_rate_kw=100.0
    )

    result = optimizer.solve(opt_input)

    assert result.solver_status == "Optimal"
    assert len(result.optimized_grid_kw) == 48
    assert len(result.battery_charge_kw) == 48
    assert len(result.battery_discharge_kw) == 48
    assert len(result.battery_soc_kwh) == 48

    for soc in result.battery_soc_kwh:
        assert 99.9 <= soc <= 450.1

    assert result.optimized_cost_lkr <= result.baseline_cost_lkr
    assert result.net_savings_lkr >= 0.0

def test_member4_milp_solver_status():
    """Checks whether Member 4 has implemented solve() or still has the TODO scaffold."""
    optimizer = CampusMicrogridOptimizer()
    opt_input = OptimizationInput(
        time_slots=["12:00"],
        base_load_kw=[300.0],
        solar_gen_kw=[100.0],
        grid_tariff_lkr_kwh=[30.0]
    )
    try:
        res = optimizer.solve(opt_input)
        assert res.solver_status == "Optimal"
    except NotImplementedError:
        pytest.skip("Member 4 has not implemented solve() yet.")
