"""
Unit tests for Member 4 (Agent 4: Mixed-Integer Linear Programming Dispatch Solver).
Terminal Command to run:
    pytest tests/unit/test_member4_milp_solver.py -v
"""

import math

import pytest
from src.agents.dispatch_explanation.milp_solver import CampusMicrogridOptimizer
from src.agents.dispatch_explanation.tier_guardrails import TierPolicy, synthetic_tier_loads
from src.domain.entities.optimization import OptimizationInput, OptimizationResult
from src.domain.exceptions.base import DomainException, InfeasibleOptimizationError

SLOTS = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]
DEMAND = [300.0 + (350.0 if 8 <= h <= 17 else 0.0) + (150.0 if 18 <= h < 22 else 0.0) for h in range(24) for _ in (0, 30)]
SOLAR = [200.0 if 9 <= h <= 15 else 0.0 for h in range(24) for _ in (0, 30)]
TARIFFS = [58.0 if 18 <= h < 23 else (15.0 if h < 6 else 30.0) for h in range(24) for _ in (0, 30)]
PEAK_SLOTS = {i for i, t in enumerate(TARIFFS) if t == 58.0}


def _input(**overrides) -> OptimizationInput:
    fields = dict(time_slots=SLOTS, base_load_kw=DEMAND, solar_gen_kw=SOLAR, grid_tariff_lkr_kwh=TARIFFS,
                  battery_capacity_kwh=500.0, max_charge_rate_kw=100.0, max_discharge_rate_kw=100.0)
    fields.update(overrides)
    return OptimizationInput(**fields)


def _tiered_input(**overrides) -> OptimizationInput:
    loads = synthetic_tier_loads(DEMAND)
    return _input(tier0_load_kw=loads.tier0_kw, tier1_load_kw=loads.tier1_kw, tier2_load_kw=loads.tier2_kw, **overrides)


def test_member4_milp_solver_48_intervals():
    result = CampusMicrogridOptimizer(battery_cap_kwh=500.0, max_kw=100.0).solve(_input())

    assert isinstance(result, OptimizationResult)
    assert result.solver_status == "Optimal"
    for series in (result.optimized_grid_kw, result.battery_charge_kw, result.battery_discharge_kw, result.battery_soc_kwh):
        assert len(series) == 48
    for soc in result.battery_soc_kwh:
        assert 99.9 <= soc <= 450.1, f"SOC {soc} kWh outside 20%-90% limits"
    assert result.optimized_cost_lkr <= result.baseline_cost_lkr
    assert result.net_savings_lkr >= 0.0


def test_binary_variable_prevents_simultaneous_charge_and_discharge():
    result = CampusMicrogridOptimizer().solve(_input())
    assert all(c < 1e-6 or d < 1e-6 for c, d in zip(result.battery_charge_kw, result.battery_discharge_kw))


def test_battery_ends_the_day_with_at_least_its_starting_charge():
    result = CampusMicrogridOptimizer().solve(_input(initial_soc_ratio=0.6))
    assert result.battery_soc_kwh[-1] >= 300.0 - 1e-6


@pytest.mark.parametrize("overrides, fragment", [
    ({"base_load_kw": DEMAND[:-1] + [math.nan]}, "base_load_kw"),
    ({"base_load_kw": DEMAND[:-1] + [-5.0]}, "base_load_kw"),
    ({"solar_gen_kw": SOLAR[:-1] + [math.inf]}, "solar_gen_kw"),
    ({"grid_tariff_lkr_kwh": TARIFFS[:-1] + [-1.0]}, "grid_tariff_lkr_kwh"),
    ({"base_load_kw": DEMAND[:10]}, "length mismatch"),
    ({"peak_demand_penalty_lkr_kva": -100.0}, "maximum-demand charge"),
    ({"min_soc_ratio": 0.9, "max_soc_ratio": 0.2, "initial_soc_ratio": 0.5}, "minimum state of charge"),
    ({"max_grid_import_kw": 0.0}, "grid import limit"),
])
def test_invalid_input_is_rejected_before_solving(overrides, fragment):
    with pytest.raises(DomainException) as exc:
        CampusMicrogridOptimizer().solve(_input(**overrides))
    assert fragment in str(exc.value)
    assert exc.value.error_code == "OPTIMIZATION_INPUT_INVALID"


def test_binding_limits_carry_their_economic_value():
    result = CampusMicrogridOptimizer().solve(_input())
    names = {b.name for b in result.binding_constraints}
    assert "End-of-Day Charge" in names
    terminal = next(b for b in result.binding_constraints if b.name == "End-of-Day Charge")
    # Requiring the battery to end the day full costs money, so its shadow price is positive.
    assert terminal.economic_impact_lkr is not None and terminal.economic_impact_lkr > 0
    assert all(b.economic_impact_lkr is None or b.economic_impact_lkr >= 0 for b in result.binding_constraints)


def test_without_tier_loads_there_is_no_tier_report():
    assert CampusMicrogridOptimizer().solve_detailed(_input()).tier_report is None


def test_tier0_is_served_in_full_and_moved_energy_is_recovered_the_same_day():
    solution = CampusMicrogridOptimizer().solve_detailed(_tiered_input(), TierPolicy(tier1_kw_per_degree_c=20.0), "synthetic")
    report = solution.tier_report
    loads = synthetic_tier_loads(DEMAND)

    assert report["tier0"]["curtailed_kwh"] == 0.0 and report["tier0"]["fully_served"] is True
    # Served load never drops below the Tier 0 load in any interval.
    assert all(served >= t0 - 1e-6 for served, t0 in zip(report["served_load_kw"], loads.tier0_kw))
    assert report["tier2"]["shifted_kwh"] == pytest.approx(report["tier2"]["recovered_kwh"], abs=0.05)
    assert report["tier1"]["reduced_kwh"] == pytest.approx(report["tier1"]["recovered_kwh"], abs=0.05)
    assert report["load_split_source"] == "synthetic"


def test_tier1_flex_is_bounded_and_only_used_in_the_peak_window():
    policy = TierPolicy(tier1_kw_per_degree_c=20.0, tier1_max_flex_c=1.5)  # at most 30 kW of reduction
    report = CampusMicrogridOptimizer().solve_detailed(_tiered_input(), policy).tier_report
    schedule = report["tier1"]["schedule_kw"]
    for t, change in enumerate(schedule):
        if change < 0:
            assert t in PEAK_SLOTS, f"Tier 1 reduced outside the peak window at {SLOTS[t]}"
            assert -change <= 30.0 + 1e-6
    assert report["tier1"]["max_reduction_kw"] <= 30.0 + 1e-6


def test_tier1_does_not_flex_without_the_digital_twin_sensitivity():
    report = CampusMicrogridOptimizer().solve_detailed(_tiered_input(), TierPolicy()).tier_report
    assert report["tier1"]["flex_enabled"] is False
    assert report["tier1"]["reduced_kwh"] == 0.0


def test_grid_import_limit_is_never_exceeded():
    result = CampusMicrogridOptimizer().solve(_tiered_input(max_grid_import_kw=600.0))
    assert max(result.optimized_grid_kw) <= 600.0 + 1e-6


def test_impossible_grid_limit_fails_safe_instead_of_cutting_tier0():
    with pytest.raises(InfeasibleOptimizationError) as exc:
        CampusMicrogridOptimizer().solve_detailed(_tiered_input(max_grid_import_kw=150.0))
    assert "Tier 0" in exc.value.details["reason"]


def test_tier_loads_must_add_up_to_the_campus_load():
    loads = synthetic_tier_loads(DEMAND)
    bad_tier2 = [v + 10.0 for v in loads.tier2_kw]
    with pytest.raises(DomainException) as exc:
        CampusMicrogridOptimizer().solve_detailed(_input(
            tier0_load_kw=loads.tier0_kw, tier1_load_kw=loads.tier1_kw, tier2_load_kw=bad_tier2))
    assert exc.value.error_code == "TIER_LOAD_INVALID"


def test_load_flexibility_never_costs_more_than_battery_only():
    optimizer = CampusMicrogridOptimizer()
    battery_only = optimizer.solve(_input())
    tiered = optimizer.solve_detailed(_tiered_input(), TierPolicy(tier1_kw_per_degree_c=20.0)).result
    assert tiered.optimized_cost_lkr <= battery_only.optimized_cost_lkr + 0.01
