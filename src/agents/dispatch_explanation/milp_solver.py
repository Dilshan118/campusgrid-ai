"""
CampusGrid AI: Agent 4 — Mixed-Integer Linear Programming (MILP) Dispatch Solver
Module Owner: Member 4 (Operations Research, Linear Optimization & Responsible AI)

RESPONSIBILITIES:
1. Formulate deterministic 48-interval microgrid cost minimization using PuLP:
   - Objective: Minimize total daily energy import cost (LKR) + peak demand surcharge penalty.
   - Variables: grid_kw[t], charge_kw[t], discharge_kw[t], soc_kwh[t], peak_grid_kw.
2. Enforce electrochemical battery constraints:
   - SOC limits: 20% to 90% of nominal capacity (e.g. 100 kWh to 450 kWh for 500 kWh battery).
   - Max charge/discharge rate: 100 kW.
   - Round-trip efficiency losses: 92% (one-way eta = sqrt(0.92)).
3. Enforce campus power balance at every 30-minute interval:
   - Grid[t] + Solar[t] + Discharge[t] >= Demand[t] + Charge[t].
4. End the day with at least the starting charge, so savings never come from simply
   emptying the battery (energy that would have to be bought back tomorrow).
5. Return verified `OptimizationResult` containing schedule, costs, savings, and binding constraints.
   Costs are per day: energy cost + the daily share (1/30) of the monthly maximum-demand charge,
   the same quantity the objective minimises.
"""

import time
from typing import List
import pulp
from src.domain.entities.optimization import OptimizationInput, OptimizationResult, BindingConstraint
from src.domain.exceptions.base import DomainException, InfeasibleOptimizationError
from src.domain.interfaces.optimizer import MicrogridOptimizerInterface

# Tolerance (kW / kWh) for treating a variable as "at its bound" when reporting
# binding constraints. Mirrors the reference baseline's own use of a flat 0.5
# margin rather than exact floating-point equality.
_BOUND_TOLERANCE = 0.5


class CampusMicrogridOptimizer(MicrogridOptimizerInterface):
    """
    Deterministic PuLP Mixed-Integer Optimization Solver.
    Assigned to: Member 4
    """

    def __init__(self, battery_cap_kwh: float = 500.0, max_kw: float = 100.0):
        # Site battery (from settings via the container). Used for any battery field the caller's
        # OptimizationInput leaves unset; explicitly supplied values (e.g. the dispatch form) win.
        self.battery_cap_kwh = battery_cap_kwh
        self.max_kw = max_kw

    def _with_site_battery(self, opt_input: OptimizationInput) -> OptimizationInput:
        site = {
            "battery_capacity_kwh": self.battery_cap_kwh,
            "max_charge_rate_kw": self.max_kw,
            "max_discharge_rate_kw": self.max_kw,
        }
        unset = {k: v for k, v in site.items() if k not in opt_input.model_fields_set}
        return opt_input.model_copy(update=unset) if unset else opt_input

    def solve(self, opt_input: OptimizationInput) -> OptimizationResult:
        """
        Formulates and solves the 48-interval microgrid dispatch problem as a
        genuine MILP: continuous power/SOC variables plus a binary per interval
        that forces the battery to either charge or discharge, never both.
        """
        start_time = time.perf_counter()
        opt_input = self._with_site_battery(opt_input)

        T = len(opt_input.time_slots)
        if not (len(opt_input.base_load_kw) == T
                and len(opt_input.solar_gen_kw) == T
                and len(opt_input.grid_tariff_lkr_kwh) == T):
            raise DomainException(
                message=(
                    "OptimizationInput series length mismatch: "
                    f"time_slots={T}, base_load_kw={len(opt_input.base_load_kw)}, "
                    f"solar_gen_kw={len(opt_input.solar_gen_kw)}, "
                    f"grid_tariff_lkr_kwh={len(opt_input.grid_tariff_lkr_kwh)}"
                ),
                error_code="OPTIMIZATION_INPUT_INVALID",
                details={
                    "time_slots_len": T,
                    "base_load_kw_len": len(opt_input.base_load_kw),
                    "solar_gen_kw_len": len(opt_input.solar_gen_kw),
                    "grid_tariff_lkr_kwh_len": len(opt_input.grid_tariff_lkr_kwh),
                },
            )

        dt = 0.5  # 30-minute interval, matches the project's 48-interval horizon

        prob = pulp.LpProblem("Campus_Microgrid_Dispatch", pulp.LpMinimize)

        # --- Continuous decision variables ---
        # grid_kw: power imported from the utility grid, per interval.
        grid_kw = [pulp.LpVariable(f"grid_{t}", lowBound=0.0) for t in range(T)]
        # charge_kw / discharge_kw: battery power flow, bounded by the rated
        # max charge/discharge rate from the request.
        charge_kw = [
            pulp.LpVariable(f"charge_{t}", lowBound=0.0, upBound=opt_input.max_charge_rate_kw)
            for t in range(T)
        ]
        discharge_kw = [
            pulp.LpVariable(f"discharge_{t}", lowBound=0.0, upBound=opt_input.max_discharge_rate_kw)
            for t in range(T)
        ]
        # soc_kwh: battery state of charge, hard-bounded to the 20%-90% safe
        # band by construction (variable bounds, not a separate constraint).
        soc_kwh = [
            pulp.LpVariable(
                f"soc_{t}",
                lowBound=opt_input.battery_capacity_kwh * opt_input.min_soc_ratio,
                upBound=opt_input.battery_capacity_kwh * opt_input.max_soc_ratio,
            )
            for t in range(T)
        ]
        # peak_grid_kw: single scalar tracking the worst interval's grid draw,
        # which the monthly demand penalty is charged against.
        peak_grid = pulp.LpVariable("peak_grid_kw", lowBound=0.0)

        # --- Binary decision variable (this is what makes the model a MILP) ---
        # is_charging[t] = 1 -> battery may charge, discharge forced to 0.
        # is_charging[t] = 0 -> battery may discharge, charge forced to 0.
        is_charging = [pulp.LpVariable(f"is_charging_{t}", cat="Binary") for t in range(T)]

        eta = opt_input.round_trip_efficiency ** 0.5  # one-way efficiency
        initial_soc = opt_input.battery_capacity_kwh * opt_input.initial_soc_ratio

        # --- Objective: energy import cost + peak demand surcharge ---
        energy_cost = pulp.lpSum(
            grid_kw[t] * opt_input.grid_tariff_lkr_kwh[t] * dt for t in range(T)
        )
        peak_surcharge = peak_grid * (opt_input.peak_demand_penalty_lkr_kva / 30.0)
        prob += energy_cost + peak_surcharge

        for t in range(T):
            # Power balance: supply (grid + solar + battery discharge) must
            # cover demand (base load + battery charge) at every interval.
            prob += (
                grid_kw[t] + opt_input.solar_gen_kw[t] + discharge_kw[t]
                >= opt_input.base_load_kw[t] + charge_kw[t]
            ), f"Power_Balance_{t}"

            # Peak tracking: peak_grid is pushed to the max grid_kw[t] because
            # it carries a positive cost in the objective above.
            prob += (peak_grid >= grid_kw[t]), f"Peak_Tracking_{t}"

            # SOC transition: charging adds energy at efficiency eta, discharging
            # removes energy at a loss (divided by eta).
            prev_soc = initial_soc if t == 0 else soc_kwh[t - 1]
            prob += (
                soc_kwh[t] == prev_soc + (charge_kw[t] * eta - discharge_kw[t] / eta) * dt
            ), f"SOC_Continuity_{t}"

            # Charge/discharge mutual exclusivity, enforced by the binary
            # variable: whichever mode is off has its rate forced to zero.
            prob += charge_kw[t] <= opt_input.max_charge_rate_kw * is_charging[t], f"Charge_Exclusivity_{t}"
            prob += (
                discharge_kw[t] <= opt_input.max_discharge_rate_kw * (1 - is_charging[t])
            ), f"Discharge_Exclusivity_{t}"

        # End-of-day energy: without this the cheapest "plan" empties the battery and books the
        # stored energy as savings, although it must be bought back the next day.
        if T > 0:
            prob += soc_kwh[T - 1] >= initial_soc, "Terminal_SOC"

        solver = pulp.PULP_CBC_CMD(msg=False)
        status = prob.solve(solver)
        solver_status = pulp.LpStatus[status]

        if solver_status != "Optimal":
            raise InfeasibleOptimizationError(
                message=f"MILP solver terminated with non-optimal status: {solver_status}",
                details={"solver_status": solver_status},
            )

        res_grid = [round(float(pulp.value(grid_kw[t])), 2) for t in range(T)]
        res_charge = [round(float(pulp.value(charge_kw[t])), 2) for t in range(T)]
        res_discharge = [round(float(pulp.value(discharge_kw[t])), 2) for t in range(T)]
        res_soc = [round(float(pulp.value(soc_kwh[t])), 2) for t in range(T)]

        opt_energy_cost = sum(res_grid[t] * opt_input.grid_tariff_lkr_kwh[t] * dt for t in range(T))
        baseline_energy_cost = sum(
            max(0.0, opt_input.base_load_kw[t] - opt_input.solar_gen_kw[t]) * opt_input.grid_tariff_lkr_kwh[t] * dt
            for t in range(T)
        )

        peak_base = max(max(0.0, opt_input.base_load_kw[t] - opt_input.solar_gen_kw[t]) for t in range(T))
        peak_opt = max(res_grid)

        # Same cost the objective minimises: energy + daily share of the monthly demand charge
        # (kW treated as kVA, i.e. unity power factor). Negative savings are reported, not hidden.
        daily_demand_rate = opt_input.peak_demand_penalty_lkr_kva / 30.0
        baseline_cost = baseline_energy_cost + peak_base * daily_demand_rate
        opt_cost = opt_energy_cost + peak_opt * daily_demand_rate
        energy_savings = baseline_energy_cost - opt_energy_cost
        demand_savings = (peak_base - peak_opt) * daily_demand_rate
        net_savings = baseline_cost - opt_cost
        savings_pct = (net_savings / baseline_cost * 100.0) if baseline_cost > 0 else 0.0

        min_soc_kwh = opt_input.battery_capacity_kwh * opt_input.min_soc_ratio
        max_soc_kwh = opt_input.battery_capacity_kwh * opt_input.max_soc_ratio

        binding: List[BindingConstraint] = []
        for t in range(T):
            if res_discharge[t] >= opt_input.max_discharge_rate_kw - _BOUND_TOLERANCE:
                binding.append(BindingConstraint(
                    name="Max Discharge Rate",
                    time_slot=opt_input.time_slots[t],
                    threshold=opt_input.max_discharge_rate_kw,
                    actual_value=res_discharge[t],
                ))
            if res_charge[t] >= opt_input.max_charge_rate_kw - _BOUND_TOLERANCE:
                binding.append(BindingConstraint(
                    name="Max Charge Rate",
                    time_slot=opt_input.time_slots[t],
                    threshold=opt_input.max_charge_rate_kw,
                    actual_value=res_charge[t],
                ))
            if res_soc[t] <= min_soc_kwh + _BOUND_TOLERANCE:
                binding.append(BindingConstraint(
                    name="Min SOC Reached",
                    time_slot=opt_input.time_slots[t],
                    threshold=min_soc_kwh,
                    actual_value=res_soc[t],
                ))
            if res_soc[t] >= max_soc_kwh - _BOUND_TOLERANCE:
                binding.append(BindingConstraint(
                    name="Max SOC Reached",
                    time_slot=opt_input.time_slots[t],
                    threshold=max_soc_kwh,
                    actual_value=res_soc[t],
                ))

        solve_duration_ms = (time.perf_counter() - start_time) * 1000.0

        return OptimizationResult(
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
            binding_constraints=binding[:5],
        )
