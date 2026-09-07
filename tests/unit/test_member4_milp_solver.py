"""
Unit tests for Member 4 (Agent 4: Mixed-Integer Linear Programming Dispatch Solver).
Terminal Command to run:
    pytest tests/unit/test_member4_milp_solver.py -v
"""

import pytest
from src.agents.dispatch_explanation.milp_solver import CampusMicrogridOptimizer
from src.domain.entities.optimization import OptimizationInput, OptimizationResult

def test_member4_milp_solver_48_intervals():
    optimizer = CampusMicrogridOptimizer(battery_cap_kwh=500.0, max_kw=100.0)

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

    try:
        result = optimizer.solve(opt_input)
    except NotImplementedError:
        pytest.skip("Member 4 has not implemented CampusMicrogridOptimizer.solve() yet.")

    assert isinstance(result, OptimizationResult)
    assert result.solver_status == "Optimal"
    assert len(result.optimized_grid_kw) == 48
    assert len(result.battery_charge_kw) == 48
    assert len(result.battery_discharge_kw) == 48
    assert len(result.battery_soc_kwh) == 48

    # Battery SOC bounds validation
    for soc in result.battery_soc_kwh:
        assert 99.9 <= soc <= 450.1, f"SOC {soc} kWh outside 20%-90% limits"

    # Savings validation
    assert result.optimized_cost_lkr <= result.baseline_cost_lkr
    assert result.net_savings_lkr >= 0.0
