"""
CampusGrid AI: Agent 4 — Mixed-Integer Linear Programming (MILP) Dispatch Solver
Module Owner: Member 4 (Operations Research, Linear Optimization & Responsible AI)

RESPONSIBILITIES:
1. Formulate deterministic 48-interval microgrid cost minimization using PuLP:
   - Objective: Minimize total daily energy import cost (LKR) + peak demand surcharge penalty.
   - Variables: grid_kw[t], charge_kw[t], discharge_kw[t], soc_kwh[t], peak_grid_kw, and the
     binary is_charging[t] that makes this a genuine MILP.
2. Enforce electrochemical battery constraints:
   - SOC limits: 20% to 90% of nominal capacity (e.g. 100 kWh to 450 kWh for 500 kWh battery).
   - Max charge/discharge rate: 100 kW.
   - Round-trip efficiency losses: 92% (one-way eta = sqrt(0.92)).
3. Enforce campus power balance at every 30-minute interval:
   - Grid[t] + Solar[t] + Discharge[t] >= ServedLoad[t] + Charge[t].
4. End the day with at least the starting charge, so savings never come from simply
   emptying the battery (energy that would have to be bought back tomorrow).
5. Enforce the fairness tiers when per-tier load is supplied (tier_guardrails.py):
   Tier 0 is never curtailed, Tier 1 flexes a bounded amount in peak intervals and pays the
   energy back, Tier 2 is shifted and recovered the same day. Optional grid import cap.
6. Return verified `OptimizationResult` containing schedule, costs, savings, and binding constraints.
   Costs are per day: energy cost + the daily share (1/30) of the monthly maximum-demand charge,
   the same quantity the objective minimises.
7. Price each binding limit: after the MILP solves, the binaries are fixed and the LP is
   re-solved to read shadow prices — "one more kW of discharge rating would save LKR X per day".
"""

import math
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pulp

from src.agents.dispatch_explanation.tier_guardrails import TierLoads, TierPolicy
from src.domain.entities.optimization import OptimizationInput, OptimizationResult, BindingConstraint
from src.domain.exceptions.base import DomainException, InfeasibleOptimizationError
from src.domain.interfaces.optimizer import MicrogridOptimizerInterface

# Tolerance (kW / kWh) for treating a variable as "at its bound" when reporting
# binding constraints. Mirrors the reference baseline's own use of a flat 0.5
# margin rather than exact floating-point equality.
_BOUND_TOLERANCE = 0.5
_DT_HOURS = 0.5  # 30-minute interval, matches the project's 48-interval horizon
_MAX_BINDING_PER_KIND = 12
# Rounding slack (kW) for the post-solve Tier 0 check; reported values are rounded to 0.01 kW.
_TIER0_CHECK_TOLERANCE_KW = 0.02


@dataclass
class DispatchSolution:
    """The solver's full answer: the contract result plus the fairness-tier report."""
    result: OptimizationResult
    tier_report: Optional[Dict[str, Any]] = None


def _invalid(message: str, **details) -> DomainException:
    return DomainException(message=message, error_code="OPTIMIZATION_INPUT_INVALID", details=details)


def validate_input(opt_input: OptimizationInput) -> None:
    """Rejects input the solver would otherwise turn into a confident but meaningless plan."""
    T = len(opt_input.time_slots)
    if T == 0:
        raise _invalid("OptimizationInput has no time slots.")
    if not (len(opt_input.base_load_kw) == T
            and len(opt_input.solar_gen_kw) == T
            and len(opt_input.grid_tariff_lkr_kwh) == T):
        raise _invalid(
            "OptimizationInput series length mismatch: "
            f"time_slots={T}, base_load_kw={len(opt_input.base_load_kw)}, "
            f"solar_gen_kw={len(opt_input.solar_gen_kw)}, "
            f"grid_tariff_lkr_kwh={len(opt_input.grid_tariff_lkr_kwh)}",
            time_slots_len=T,
            base_load_kw_len=len(opt_input.base_load_kw),
            solar_gen_kw_len=len(opt_input.solar_gen_kw),
            grid_tariff_lkr_kwh_len=len(opt_input.grid_tariff_lkr_kwh),
        )
    for name, series in (("base_load_kw", opt_input.base_load_kw),
                         ("solar_gen_kw", opt_input.solar_gen_kw),
                         ("grid_tariff_lkr_kwh", opt_input.grid_tariff_lkr_kwh)):
        bad = [i for i, v in enumerate(series) if not math.isfinite(v) or v < 0]
        if bad:
            raise _invalid(f"{name} must be finite and non-negative (interval {bad[0]}: {series[bad[0]]}).",
                           series=name, interval=bad[0])
    if not math.isfinite(opt_input.peak_demand_penalty_lkr_kva) or opt_input.peak_demand_penalty_lkr_kva < 0:
        raise _invalid("The maximum-demand charge must be finite and non-negative.")
    if opt_input.min_soc_ratio >= opt_input.max_soc_ratio:
        raise _invalid("The battery's minimum state of charge must be below its maximum.")
    if not opt_input.min_soc_ratio <= opt_input.initial_soc_ratio <= opt_input.max_soc_ratio:
        raise _invalid("The battery's starting charge is outside its state-of-charge band.")
    if opt_input.max_grid_import_kw is not None and not opt_input.max_grid_import_kw > 0:
        raise _invalid("The grid import limit must be positive.")


class CampusMicrogridOptimizer(MicrogridOptimizerInterface):
    """
    Deterministic PuLP Mixed-Integer Optimization Solver.
    Assigned to: Member 4
    """

    def __init__(self, battery_cap_kwh: float = 500.0, max_kw: float = 100.0, tier_policy: Optional[TierPolicy] = None):
        # Site battery (from settings via the container). Used for any battery field the caller's
        # OptimizationInput leaves unset; explicitly supplied values (e.g. the dispatch form) win.
        self.battery_cap_kwh = battery_cap_kwh
        self.max_kw = max_kw
        self.tier_policy = tier_policy or TierPolicy()

    def _with_site_battery(self, opt_input: OptimizationInput) -> OptimizationInput:
        site = {
            "battery_capacity_kwh": self.battery_cap_kwh,
            "max_charge_rate_kw": self.max_kw,
            "max_discharge_rate_kw": self.max_kw,
        }
        unset = {k: v for k, v in site.items() if k not in opt_input.model_fields_set}
        return opt_input.model_copy(update=unset) if unset else opt_input

    def solve(self, opt_input: OptimizationInput) -> OptimizationResult:
        """Contract entry point (MicrogridOptimizerInterface): the schedule and its costs."""
        return self.solve_detailed(opt_input).result

    def solve_detailed(
        self,
        opt_input: OptimizationInput,
        tier_policy: Optional[TierPolicy] = None,
        tier_source: str = "provided",
    ) -> DispatchSolution:
        """
        Formulates and solves the 48-interval microgrid dispatch problem as a
        genuine MILP: continuous power/SOC variables plus a binary per interval
        that forces the battery to either charge or discharge, never both.
        Tier constraints are added when opt_input carries all three tier load series.
        """
        start_time = time.perf_counter()
        opt_input = self._with_site_battery(opt_input)
        validate_input(opt_input)
        policy = tier_policy or self.tier_policy

        T = len(opt_input.time_slots)
        dt = _DT_HOURS
        tariffs = opt_input.grid_tariff_lkr_kwh
        tiers_on = all(s is not None for s in (opt_input.tier0_load_kw, opt_input.tier1_load_kw, opt_input.tier2_load_kw))
        if tiers_on:
            TierLoads(opt_input.tier0_load_kw, opt_input.tier1_load_kw, opt_input.tier2_load_kw, tier_source) \
                .validate_against(opt_input.base_load_kw)

        prob = pulp.LpProblem("Campus_Microgrid_Dispatch", pulp.LpMinimize)

        # --- Continuous decision variables ---
        # grid_kw: power imported from the utility grid, per interval.
        grid_kw = [pulp.LpVariable(f"grid_{t}", lowBound=0.0) for t in range(T)]
        # charge_kw / discharge_kw: battery power flow; the rated limits are enforced by the
        # exclusivity constraints below, so their shadow prices can be read.
        charge_kw = [pulp.LpVariable(f"charge_{t}", lowBound=0.0) for t in range(T)]
        discharge_kw = [pulp.LpVariable(f"discharge_{t}", lowBound=0.0) for t in range(T)]
        # soc_kwh: battery state of charge. The 20%-90% band is written as explicit constraints
        # (SOC_Min_t / SOC_Max_t) rather than variable bounds, for the same reason.
        soc_kwh = [pulp.LpVariable(f"soc_{t}") for t in range(T)]
        # peak_grid_kw: single scalar tracking the worst interval's grid draw,
        # which the monthly demand penalty is charged against.
        peak_grid = pulp.LpVariable("peak_grid_kw", lowBound=0.0)

        # --- Binary decision variable (this is what makes the model a MILP) ---
        # is_charging[t] = 1 -> battery may charge, discharge forced to 0.
        # is_charging[t] = 0 -> battery may discharge, charge forced to 0.
        is_charging = [pulp.LpVariable(f"is_charging_{t}", cat="Binary") for t in range(T)]

        eta = opt_input.round_trip_efficiency ** 0.5  # one-way efficiency
        initial_soc = opt_input.battery_capacity_kwh * opt_input.initial_soc_ratio
        min_soc_kwh = opt_input.battery_capacity_kwh * opt_input.min_soc_ratio
        max_soc_kwh = opt_input.battery_capacity_kwh * opt_input.max_soc_ratio

        # --- Fairness tiers: how much of each interval's load may move ---
        served_load = [opt_input.base_load_kw[t] for t in range(T)]  # constants, or expressions below
        t1_red = t1_pay = t2_down = t2_up = None
        flex_penalty = 0
        peak_slots: List[int] = []
        tier1_cap_kw = 0.0
        if tiers_on:
            tier1 = opt_input.tier1_load_kw
            tier2 = opt_input.tier2_load_kw
            # Tier 1 may only flex in the highest-tariff intervals (the peak window), and only if
            # the digital twin's kW-per-degree figure is known.
            if max(tariffs) > min(tariffs):
                peak_slots = [t for t in range(T) if tariffs[t] >= max(tariffs) - 1e-9]
            if policy.tier1_kw_per_degree_c:
                tier1_cap_kw = policy.tier1_kw_per_degree_c * policy.tier1_max_flex_c
            t1_red = [
                pulp.LpVariable(f"tier1_reduce_{t}", lowBound=0.0,
                                upBound=min(tier1_cap_kw, tier1[t]) if t in peak_slots else 0.0)
                for t in range(T)
            ]
            t1_pay = [
                pulp.LpVariable(f"tier1_payback_{t}", lowBound=0.0,
                                upBound=0.0 if t in peak_slots else tier1_cap_kw)
                for t in range(T)
            ]
            # Tier 2: shift down (curtail) and up (recover), capped at a multiple of its peak.
            tier2_ceiling = policy.tier2_max_rebound_ratio * max(tier2)
            t2_down = [pulp.LpVariable(f"tier2_shift_down_{t}", lowBound=0.0, upBound=tier2[t]) for t in range(T)]
            t2_up = [pulp.LpVariable(f"tier2_shift_up_{t}", lowBound=0.0, upBound=max(0.0, tier2_ceiling - tier2[t]))
                     for t in range(T)]
            # Tier 0 has no variable at all: its load is a constant inside served_load, so no
            # value of any decision variable can reduce it.
            served_load = [
                opt_input.base_load_kw[t] - t1_red[t] + t1_pay[t] - t2_down[t] + t2_up[t]
                for t in range(T)
            ]
            # SEC-06: the tier split may differ from the campus load by the validation tolerance, so
            # the reductions are also capped by what is left above Tier 0 in the campus load itself.
            # This states the invariant directly instead of relying on the split adding up.
            for t in range(T):
                prob += (
                    t1_red[t] + t2_down[t] <= max(0.0, opt_input.base_load_kw[t] - opt_input.tier0_load_kw[t])
                ), f"Tier0_Floor_{t}"
            # Energy moved is energy recovered the same day (D-3): nothing is dropped.
            prob += pulp.lpSum(t1_pay) == pulp.lpSum(t1_red), "Tier1_Energy_Payback"
            prob += pulp.lpSum(t2_up) == pulp.lpSum(t2_down), "Tier2_Same_Day_Recovery"
            flex_penalty = pulp.lpSum(
                (t1_red[t] + t1_pay[t]) * policy.tier1_flex_cost_lkr_kwh * dt
                + (t2_down[t] + t2_up[t]) * policy.tier2_shift_cost_lkr_kwh * dt
                for t in range(T)
            )

        # --- Objective: energy import cost + peak demand surcharge (+ small flexibility costs) ---
        energy_cost = pulp.lpSum(grid_kw[t] * tariffs[t] * dt for t in range(T))
        peak_surcharge = peak_grid * (opt_input.peak_demand_penalty_lkr_kva / 30.0)
        prob += energy_cost + peak_surcharge + flex_penalty

        for t in range(T):
            # Power balance: supply (grid + solar + battery discharge) must
            # cover demand (served load + battery charge) at every interval.
            prob += (
                grid_kw[t] + opt_input.solar_gen_kw[t] + discharge_kw[t]
                >= served_load[t] + charge_kw[t]
            ), f"Power_Balance_{t}"

            # Peak tracking: peak_grid is pushed to the max grid_kw[t] because
            # it carries a positive cost in the objective above.
            prob += (peak_grid >= grid_kw[t]), f"Peak_Tracking_{t}"

            if opt_input.max_grid_import_kw is not None:
                prob += grid_kw[t] <= opt_input.max_grid_import_kw, f"Grid_Import_Limit_{t}"

            # SOC transition: charging adds energy at efficiency eta, discharging
            # removes energy at a loss (divided by eta).
            prev_soc = initial_soc if t == 0 else soc_kwh[t - 1]
            prob += (
                soc_kwh[t] == prev_soc + (charge_kw[t] * eta - discharge_kw[t] / eta) * dt
            ), f"SOC_Continuity_{t}"
            prob += soc_kwh[t] >= min_soc_kwh, f"SOC_Min_{t}"
            prob += soc_kwh[t] <= max_soc_kwh, f"SOC_Max_{t}"

            # Charge/discharge mutual exclusivity and rated limits, enforced by the binary
            # variable: whichever mode is off has its rate forced to zero.
            prob += charge_kw[t] <= opt_input.max_charge_rate_kw * is_charging[t], f"Charge_Exclusivity_{t}"
            prob += (
                discharge_kw[t] <= opt_input.max_discharge_rate_kw * (1 - is_charging[t])
            ), f"Discharge_Exclusivity_{t}"

        # End-of-day energy: without this the cheapest "plan" empties the battery and books the
        # stored energy as savings, although it must be bought back the next day.
        prob += soc_kwh[T - 1] >= initial_soc, "Terminal_SOC"

        status = prob.solve(pulp.PULP_CBC_CMD(msg=False))
        solver_status = pulp.LpStatus[status]

        if solver_status != "Optimal":
            details: Dict[str, Any] = {"solver_status": solver_status}
            if tiers_on:
                details["tier0_peak_kw"] = round(max(opt_input.tier0_load_kw), 1)
                details["reason"] = ("Tier 0 (critical) load cannot be curtailed; the grid limit, solar and "
                                     "battery together cannot serve it with the flexibility allowed.")
            if opt_input.max_grid_import_kw is not None:
                details["max_grid_import_kw"] = opt_input.max_grid_import_kw
            raise InfeasibleOptimizationError(
                message=f"MILP solver terminated with non-optimal status: {solver_status}",
                details=details,
            )

        res_grid = [round(float(pulp.value(grid_kw[t])), 2) for t in range(T)]
        res_charge = [round(float(pulp.value(charge_kw[t])), 2) for t in range(T)]
        res_discharge = [round(float(pulp.value(discharge_kw[t])), 2) for t in range(T)]
        res_soc = [round(float(pulp.value(soc_kwh[t])), 2) for t in range(T)]
        charging_mode = [round(float(pulp.value(is_charging[t]))) for t in range(T)]

        opt_energy_cost = sum(res_grid[t] * tariffs[t] * dt for t in range(T))
        baseline_energy_cost = sum(
            max(0.0, opt_input.base_load_kw[t] - opt_input.solar_gen_kw[t]) * tariffs[t] * dt
            for t in range(T)
        )

        peak_base = max(max(0.0, opt_input.base_load_kw[t] - opt_input.solar_gen_kw[t]) for t in range(T))
        peak_opt = max(res_grid)

        # Same cost the objective minimises: energy + daily share of the monthly demand charge
        # (kW treated as kVA, i.e. unity power factor). Negative savings are reported, not hidden.
        # The small flexibility costs steer the solver but are not part of the bill.
        daily_demand_rate = opt_input.peak_demand_penalty_lkr_kva / 30.0
        baseline_cost = baseline_energy_cost + peak_base * daily_demand_rate
        opt_cost = opt_energy_cost + peak_opt * daily_demand_rate
        energy_savings = baseline_energy_cost - opt_energy_cost
        demand_savings = (peak_base - peak_opt) * daily_demand_rate
        net_savings = baseline_cost - opt_cost
        savings_pct = (net_savings / baseline_cost * 100.0) if baseline_cost > 0 else 0.0

        # Read the tier schedule before the shadow-price re-solve, which may pick a different
        # schedule of equal cost.
        tier_report = None
        if tiers_on:
            tier_report = self._tier_report(
                opt_input, policy, tier_source, peak_slots, tier1_cap_kw, t1_red, t1_pay, t2_down, t2_up,
            )

        shadow = self._shadow_prices(prob, is_charging, charging_mode)
        binding = self._binding_constraints(
            opt_input, res_grid, res_charge, res_discharge, res_soc, min_soc_kwh, max_soc_kwh, initial_soc, shadow,
        )

        solve_duration_ms = (time.perf_counter() - start_time) * 1000.0

        result = OptimizationResult(
            time_slots=opt_input.time_slots,
            optimized_grid_kw=res_grid,
            battery_charge_kw=res_charge,
            battery_discharge_kw=res_discharge,
            battery_soc_kwh=res_soc,
            baseline_cost_lkr=round(baseline_cost, 2),
            optimized_cost_lkr=round(opt_cost, 2),
            net_savings_lkr=round(net_savings, 2),
            savings_percentage=round(savings_pct, 1),
            energy_savings_lkr=round(energy_savings, 2),
            demand_charge_savings_lkr=round(demand_savings, 2),
            peak_demand_baseline_kw=round(peak_base, 1),
            peak_demand_optimized_kw=round(peak_opt, 1),
            solver_status=solver_status,
            solve_time_ms=solve_duration_ms,
            binding_constraints=binding,
        )
        return DispatchSolution(result=result, tier_report=tier_report)

    # ------------------------------------------------------------------
    # Explainability: which limits bind, and what they cost
    # ------------------------------------------------------------------

    @staticmethod
    def _shadow_prices(prob: pulp.LpProblem, is_charging, charging_mode: List[int]) -> Dict[str, float]:
        """
        Fixes every binary at its optimal value and re-solves the remaining LP, whose constraint
        duals are the marginal LKR value of each limit. The values are conditional on the chosen
        charge/discharge pattern — the usual way to price constraints in a MILP.
        Returns constraint name -> dual; empty if the LP re-solve does not succeed.
        """
        for var, mode in zip(is_charging, charging_mode):
            var.cat = pulp.LpContinuous
            var.lowBound = var.upBound = mode
        try:
            if pulp.LpStatus[prob.solve(pulp.PULP_CBC_CMD(msg=False))] != "Optimal":
                return {}
            return {name: (c.pi or 0.0) for name, c in prob.constraints.items()}
        except Exception:  # duals are an explanation aid; the plan itself is already solved
            return {}

    @staticmethod
    def _binding_constraints(
        opt_input: OptimizationInput,
        res_grid: List[float], res_charge: List[float], res_discharge: List[float], res_soc: List[float],
        min_soc_kwh: float, max_soc_kwh: float, initial_soc: float, shadow: Dict[str, float],
    ) -> List[BindingConstraint]:
        """
        One entry per interval where a limit bound (at most `_MAX_BINDING_PER_KIND` per kind, the
        dashboard groups them by name), each with `economic_impact_lkr` — LKR per day that one
        more unit of that limit in that interval (kW of rating, kWh of battery band, kW of grid
        connection) would save. None when the shadow prices could not be read.
        """
        T = len(opt_input.time_slots)
        kinds = [  # (name, threshold, is_binding(t), constraint prefix, dual sign, reported series)
            ("Max Discharge Rate", opt_input.max_discharge_rate_kw,
             lambda t: res_discharge[t] >= opt_input.max_discharge_rate_kw - _BOUND_TOLERANCE,
             "Discharge_Exclusivity_", -1.0, res_discharge),
            ("Max Charge Rate", opt_input.max_charge_rate_kw,
             lambda t: res_charge[t] >= opt_input.max_charge_rate_kw - _BOUND_TOLERANCE,
             "Charge_Exclusivity_", -1.0, res_charge),
            ("Min SOC Reached", min_soc_kwh,
             lambda t: res_soc[t] <= min_soc_kwh + _BOUND_TOLERANCE,
             "SOC_Min_", 1.0, res_soc),
            ("Max SOC Reached", max_soc_kwh,
             lambda t: res_soc[t] >= max_soc_kwh - _BOUND_TOLERANCE,
             "SOC_Max_", -1.0, res_soc),
        ]
        if opt_input.max_grid_import_kw is not None:
            cap = opt_input.max_grid_import_kw
            kinds.append(("Grid Import Limit", cap, lambda t: res_grid[t] >= cap - _BOUND_TOLERANCE,
                          "Grid_Import_Limit_", -1.0, res_grid))

        def impact(name: str, sign: float) -> Optional[float]:
            # For a <= limit the dual is <= 0 (relaxing it lowers cost); for >= it is >= 0.
            return round(sign * shadow.get(name, 0.0), 2) + 0.0 if shadow else None  # + 0.0: no "-0.0"

        binding: List[BindingConstraint] = []
        for name, threshold, is_binding, prefix, sign, series in kinds:
            slots = [t for t in range(T) if is_binding(t)][:_MAX_BINDING_PER_KIND]
            binding += [
                BindingConstraint(
                    name=name,
                    time_slot=opt_input.time_slots[t],
                    threshold=round(threshold, 2),
                    actual_value=series[t],
                    economic_impact_lkr=impact(f"{prefix}{t}", sign),
                )
                for t in slots
            ]
        if res_soc[-1] <= initial_soc + _BOUND_TOLERANCE:
            binding.append(BindingConstraint(
                name="End-of-Day Charge",
                time_slot=opt_input.time_slots[-1],
                threshold=round(initial_soc, 2),
                actual_value=res_soc[-1],
                economic_impact_lkr=impact("Terminal_SOC", 1.0),
            ))
        return binding

    @staticmethod
    def _tier_report(
        opt_input: OptimizationInput, policy: TierPolicy, source: str, peak_slots: List[int], tier1_cap_kw: float,
        t1_red, t1_pay, t2_down, t2_up,
    ) -> Dict[str, Any]:
        T = len(opt_input.time_slots)
        dt = _DT_HOURS
        val = lambda v: round(max(0.0, float(pulp.value(v) or 0.0)), 2)  # noqa: E731
        red = [val(v) for v in t1_red]
        pay = [val(v) for v in t1_pay]
        down = [val(v) for v in t2_down]
        up = [val(v) for v in t2_up]
        tier1_net = [round(pay[t] - red[t], 2) for t in range(T)]
        tier2_net = [round(up[t] - down[t], 2) for t in range(T)]
        served = [round(opt_input.base_load_kw[t] + tier1_net[t] + tier2_net[t], 2) for t in range(T)]
        # SEC-06: the Tier 0 figures are measured on the solution, not asserted. Tier 0 is curtailed
        # in an interval when the Tier 1 / Tier 2 reductions exceed the load above Tier 0 there.
        tier0_cut = [
            max(0.0, red[t] + down[t] - max(0.0, opt_input.base_load_kw[t] - opt_input.tier0_load_kw[t]))
            for t in range(T)
        ]
        curtailed_kwh = round(sum(tier0_cut) * dt, 2)
        if any(c > _TIER0_CHECK_TOLERANCE_KW for c in tier0_cut):
            # Fail closed: a plan that under-serves critical load is never returned.
            raise DomainException(
                message="Post-solve check failed: the schedule would curtail Tier 0 (critical) load.",
                error_code="TIER0_PROTECTION_VIOLATED",
                details={"curtailed_kwh": curtailed_kwh,
                         "intervals": [opt_input.time_slots[t] for t in range(T) if tier0_cut[t] > _TIER0_CHECK_TOLERANCE_KW]},
            )
        return {
            "enabled": True,
            "load_split_source": source,
            "tier0": {
                "served_kwh": round(sum(opt_input.tier0_load_kw) * dt - curtailed_kwh, 2),
                "curtailed_kwh": curtailed_kwh,
                "fully_served": True,
                "peak_kw": round(max(opt_input.tier0_load_kw), 2),
            },
            "tier1": {
                "flex_enabled": tier1_cap_kw > 0 and bool(peak_slots),
                "max_flex_c": policy.tier1_max_flex_c,
                "kw_per_degree_c": policy.tier1_kw_per_degree_c,
                "max_reduction_kw": round(max(red), 2) if red else 0.0,
                "reduced_kwh": round(sum(red) * dt, 2),
                "recovered_kwh": round(sum(pay) * dt, 2),
                "flex_window": [opt_input.time_slots[t] for t in peak_slots],
                "schedule_kw": tier1_net,
            },
            "tier2": {
                "max_shift_kw": round(max(down), 2) if down else 0.0,
                "shifted_kwh": round(sum(down) * dt, 2),
                "recovered_kwh": round(sum(up) * dt, 2),
                "schedule_kw": tier2_net,
            },
            "served_load_kw": served,
        }
