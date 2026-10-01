"""
Tier 0/1/2 enforcement inside the MILP, the grid import limit, the kVA / month-to-date demand
charge, the independent post-solve check, and the coordinator's solve -> verify -> re-solve loop.
"""

import pytest
from src.agents.coordinator.load_tiers import build_tier_profiles, scaled_hvac_schedule
from src.agents.dispatch_explanation.milp_solver import CampusMicrogridOptimizer
from src.agents.dispatch_explanation.post_solve import check_solution
from src.application.container import Container
from src.config.settings import Settings
from src.domain.entities.optimization import OptimizationInput
from src.domain.exceptions.base import DomainException, InfeasibleOptimizationError
from src.shared.datetime_utils import build_tou_tariff_profile

SLOTS = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]
BASE = [300.0 + (250.0 if 16 <= i <= 44 else 0.0) for i in range(48)]
SOLAR = [120.0 if 18 <= i <= 32 else 0.0 for i in range(48)]
TARIFF = build_tou_tariff_profile(SLOTS, 58.0, 30.0, 15.0)
PEAK_SLOTS = {i for i, s in enumerate(SLOTS) if "18:30" <= s <= "22:00"}


def _input(**extra):
    return OptimizationInput(time_slots=SLOTS, base_load_kw=BASE, solar_gen_kw=SOLAR, grid_tariff_lkr_kwh=TARIFF, **extra)


def _tiers(hvac_share=0.4, shift_kw=20.0, hours=3.0, start="18:00"):
    t = build_tier_profiles(BASE, SLOTS, hvac_share, shift_kw, hours, start)
    t.pop("notes")
    return t


# --------------------------------------------------------------------------- tier split

def test_tier_split_partitions_the_forecast():
    t = build_tier_profiles(BASE, SLOTS, 0.4, 20.0, 3.0, "23:00")
    for i in range(48):
        assert t["tier0_load_kw"][i] + t["tier1_load_kw"][i] + t["tier2_load_kw"][i] == pytest.approx(BASE[i])
    # 3 h from 23:00 wraps past midnight.
    assert {SLOTS[i] for i, v in enumerate(t["tier2_load_kw"]) if v} == {"23:00", "23:30", "00:00", "00:30", "01:00", "01:30"}
    assert t["notes"]


def test_nothing_flexible_gives_no_tiers():
    assert build_tier_profiles(BASE, SLOTS, 0.0) is None


def test_scaled_hvac_follows_the_plans_shift():
    assert scaled_hvac_schedule([10.0, 10.0, 0.0], [100.0, 100.0, 0.0], [90.0, 110.0, 0.0]) == [9.0, 11.0, 0.0]


# --------------------------------------------------------------------------- MILP tiers

def test_tier0_is_never_curtailed_and_tier_energy_is_conserved():
    tiers = _tiers()
    res = CampusMicrogridOptimizer().solve(_input(**tiers, tier1_max_reduction_ratio=0.1))
    assert res.served_tier0_kw == pytest.approx(tiers["tier0_load_kw"], abs=0.01)
    assert sum(res.served_tier1_kw) == pytest.approx(sum(tiers["tier1_load_kw"]), abs=0.5)
    assert sum(res.served_tier2_kw) == pytest.approx(sum(tiers["tier2_load_kw"]), abs=0.5)
    for served, planned in zip(res.served_tier1_kw, tiers["tier1_load_kw"]):
        assert planned * 0.9 - 0.01 <= served <= planned * 1.1 + 0.01
    assert res.post_solve_checks["passed"] is True
    assert res.post_solve_checks["tier0_curtailed_kw"] == 0.0


def test_shiftable_load_moves_out_of_the_peak_and_flexibility_saves_money():
    battery_only = CampusMicrogridOptimizer().solve(_input())
    flexible = CampusMicrogridOptimizer().solve(_input(**_tiers(start="18:30"), tier1_max_reduction_ratio=0.1))
    assert not any(flexible.served_tier2_kw[i] > 0.1 for i in PEAK_SLOTS)
    assert flexible.net_savings_lkr > battery_only.net_savings_lkr


def test_tier1_is_reduced_only_in_the_peak_window_by_the_tighter_cap():
    """TierPolicy rules: Tier 1 is cut only in the highest-tariff half-hours and paid back
    elsewhere; the cut is the tighter of the degree-based cap and the planner's ratio."""
    from src.agents.dispatch_explanation.tier_guardrails import TierPolicy
    tiers = _tiers()
    peak = {i for i in range(48) if TARIFF[i] == max(TARIFF)}
    ratio_only = CampusMicrogridOptimizer().solve(_input(**tiers, tier1_max_reduction_ratio=0.1))
    for i, (served, planned) in enumerate(zip(ratio_only.served_tier1_kw, tiers["tier1_load_kw"])):
        if i in peak:
            assert planned * 0.9 - 0.01 <= served <= planned + 0.01
        else:
            assert planned - 0.01 <= served <= planned * 1.1 + 0.01
    assert any(ratio_only.served_tier1_kw[i] < tiers["tier1_load_kw"][i] - 1.0 for i in peak)

    # 10 kW per degree x 1.5 C = 15 kW, tighter than 10% of the ~220 kW peak-window Tier 1 load.
    both = CampusMicrogridOptimizer(tier_policy=TierPolicy(tier1_kw_per_degree_c=10.0)).solve(
        _input(**tiers, tier1_max_reduction_ratio=0.1))
    assert max(p - s for s, p in zip(both.served_tier1_kw, tiers["tier1_load_kw"])) <= 15.0 + 0.01


def test_shifted_tier2_never_exceeds_its_rated_power():
    res = CampusMicrogridOptimizer().solve(_input(**_tiers(shift_kw=20.0, start="18:30"), tier2_max_kw=20.0))
    assert max(res.served_tier2_kw) <= 20.0 + 0.01
    assert res.post_solve_checks["passed"] is True


def test_fairness_note_states_only_the_configured_tier1_limit():
    from src.agents.dispatch_explanation.agent import DispatchExplanationAgent
    report = {"enabled": True, "load_split_source": "synthetic",
              "tier1": {"reduced_kwh": 5.0, "max_flex_c": 1.5, "kw_per_degree_c": None, "max_reduction_ratio": 0.1},
              "tier2": {"shifted_kwh": 0.0}}
    note = DispatchExplanationAgent._fairness_note(report)
    assert "10% of the air-conditioning load" in note
    assert "1.5 C" not in note  # no degree figure without the twin's kW per degree
    assert "synthetic" in note


def test_tiers_that_do_not_add_up_are_rejected():
    tiers = _tiers()
    tiers["tier0_load_kw"] = [v - 50 for v in tiers["tier0_load_kw"]]
    with pytest.raises(DomainException) as err:
        CampusMicrogridOptimizer().solve(_input(**tiers))
    assert err.value.error_code == "TIER_LOAD_INVALID"  # tier_guardrails.TierLoads.validate_against


def test_grid_import_limit_is_a_hard_constraint():
    res = CampusMicrogridOptimizer().solve(_input(max_grid_import_kw=520.0))
    assert max(res.optimized_grid_kw) <= 520.0 + 0.01
    with pytest.raises(InfeasibleOptimizationError):
        CampusMicrogridOptimizer().solve(_input(max_grid_import_kw=200.0))


def test_month_to_date_peak_changes_the_demand_charge_basis():
    daily_share = CampusMicrogridOptimizer().solve(_input())
    below_month_peak = CampusMicrogridOptimizer().solve(_input(month_to_date_peak_kva=900.0))
    assert "1/30" in daily_share.demand_charge_basis
    assert "month-to-date peak of 900" in below_month_peak.demand_charge_basis
    # The day cannot raise a 900 kVA month peak, so no demand charge is attributed to it at all.
    assert below_month_peak.demand_charge_savings_lkr == 0.0


def test_power_factor_raises_the_kva_demand_charge():
    unity = CampusMicrogridOptimizer().solve(_input())
    lagging = CampusMicrogridOptimizer().solve(_input(power_factor=0.8))
    assert lagging.baseline_cost_lkr > unity.baseline_cost_lkr


# --------------------------------------------------------------------------- post-solve check

def test_post_solve_check_catches_a_broken_schedule():
    opt = _input()
    res = CampusMicrogridOptimizer().solve(opt)
    grid = list(res.optimized_grid_kw)
    grid[40] -= 50.0  # supply no longer covers demand
    charge = list(res.battery_charge_kw)
    charge[2] = opt.max_charge_rate_kw + 20.0
    checks = check_solution(opt, None, grid, charge, res.battery_discharge_kw, res.battery_soc_kwh,
                            None, None, opt.round_trip_efficiency ** 0.5, 0.5)
    assert checks["passed"] is False
    joined = " | ".join(checks["failures"])
    assert "Supply below demand" in joined and "Charging above the rated limit" in joined


# --------------------------------------------------------------------------- coordinator loop

@pytest.fixture(scope="module")
def member_container():
    """Member optimizer and twin (not the reference baselines), built without replacing the app singleton."""
    return Container(Settings(app_env="test", use_reference_baselines=False, auto_baseline_fallback=False))


def _plan(container, **load):
    res = container.orchestrator.execute({
        "query": "Plan tomorrow's battery schedule for LH-1", "user_id": "tester",
        "force_full_pipeline": True, "room": "LH-1", "date": "2026-10-06", "load_parameters": load,
    })
    assert res.success, res.error
    return res.data["recommendation"]


def test_plan_enforces_tiers_and_records_the_twin_verdict(member_container):
    plan = _plan(member_container, shiftable_load_kw=20, shiftable_hours=2, shiftable_usual_start="19:00")
    assert plan["load_flexibility"]["tiers_enforced"] is True
    assert plan["post_solve_verification"]["verdict"] in ("accept", "re_optimize", "reject")
    assert plan["solver_summary"]["post_solve_checks"]["passed"] is True
    assert any("15-minute" in a for a in plan["assumptions"])
    assert any("Air-conditioning is assumed" in a for a in plan["assumptions"])


def test_hvac_flex_is_withdrawn_when_the_twin_rejects_it(member_container, monkeypatch):
    twin = member_container.agent2_twin
    real_verify = twin.verify_dispatch_plan
    calls = []

    def verify(sim_input, dispatch):
        calls.append("hvac_power_kw" in dispatch["solver_output"])
        if "hvac_power_kw" in dispatch["solver_output"]:
            return {"verdict": "re_optimize", "reasons": ["Comfort band broken in 3 interval(s)."],
                    "checks": {"is_thermal_feasible": False}}
        return real_verify(sim_input, dispatch)

    monkeypatch.setattr(twin, "verify_dispatch_plan", verify)
    plan = _plan(member_container, hvac_flex_ratio=0.10)
    assert calls == [True, False]
    assert plan["load_flexibility"]["hvac_flex_withdrawn"] is True
    assert plan["load_flexibility"]["hvac_flex_ratio"] == 0.0
    assert any("re-solved with HVAC flexibility off" in a for a in plan["assumptions"])


def test_plan_reports_tier_dispatch_and_respects_rated_shiftable_power(member_container):
    plan = _plan(member_container, hvac_flex_ratio=0.10, shiftable_load_kw=20, shiftable_hours=2, shiftable_usual_start="19:00")
    assert max(plan["solver_summary"]["served_tier2_kw"]) <= 20.0 + 0.01
    assert plan["solver_summary"]["post_solve_checks"]["tier0_curtailed_kw"] == 0.0


def test_hvac_flex_off_skips_the_tier1_shift(member_container):
    plan = _plan(member_container, hvac_flex_ratio=0.0)
    assert plan["load_flexibility"]["tiers_enforced"] is False
    assert plan["solver_summary"]["served_tier1_kw"] is None


def test_a_battery_objection_does_not_withdraw_hvac_flex(member_container, monkeypatch):
    monkeypatch.setattr(member_container.agent2_twin, "verify_dispatch_plan", lambda sim_input, dispatch: {
        "verdict": "re_optimize", "reasons": ["Battery leaves its state-of-charge band in 2 interval(s)."],
        "checks": {"is_thermal_feasible": True},
    })
    plan = _plan(member_container, hvac_flex_ratio=0.10)
    assert plan["load_flexibility"]["hvac_flex_withdrawn"] is False
    assert any("did not accept the final schedule" in w for w in plan["warnings"])


def test_a_plan_riding_the_soc_limit_is_accepted_by_the_twin(member_container):
    """Rounding put the twin at 450.01 kWh against a 450 kWh limit, flagging every such plan."""
    plan = _plan(member_container, hvac_flex_ratio=0.0)
    soc = plan["solver_summary"]["battery_soc_kwh"]
    assert max(soc) == pytest.approx(450.0, abs=0.01)
    assert plan["post_solve_verification"]["checks"]["battery_soc_violations"] == 0
