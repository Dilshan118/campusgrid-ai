"""
CampusGrid AI: Reference Baseline MILP Solver
PuLP linear/mixed-integer cost minimization and peak shaving solver.
Preserved as reference benchmark for Member 4.
"""

import time
from typing import List
import pulp
from src.domain.entities.optimization import OptimizationInput, OptimizationResult, BindingConstraint
from src.domain.exceptions.base import InfeasibleOptimizationError
from src.domain.interfaces.optimizer import MicrogridOptimizerInterface

class BaselineCampusMicrogridOptimizer(MicrogridOptimizerInterface):
    """Deterministic PuLP Linear / MILP Optimization Solver."""

    def __init__(self, battery_cap_kwh: float = 500.0, max_kw: float = 100.0):
        self.battery_cap_kwh = battery_cap_kwh
        self.max_kw = max_kw

    def solve(self, opt_input: OptimizationInput) -> OptimizationResult:
        start_time = time.time()
        T = len(opt_input.time_slots)
        dt = 0.5  # 30-minute interval

        prob = pulp.LpProblem("Campus_Microgrid_Dispatch_Baseline", pulp.LpMinimize)

        # Decision Variables
        grid_kw = [pulp.LpVariable(f"grid_{t}", lowBound=0.0) for t in range(T)]
        charge_kw = [pulp.LpVariable(f"charge_{t}", lowBound=0.0, upBound=opt_input.max_charge_rate_kw) for t in range(T)]
        discharge_kw = [pulp.LpVariable(f"discharge_{t}", lowBound=0.0, upBound=opt_input.max_discharge_rate_kw) for t in range(T)]
        soc_kwh = [
            pulp.LpVariable(
                f"soc_{t}",
                lowBound=opt_input.battery_capacity_kwh * opt_input.min_soc_ratio,
                upBound=opt_input.battery_capacity_kwh * opt_input.max_soc_ratio
            )
            for t in range(T)
        ]
        peak_grid = pulp.LpVariable("peak_grid_kw", lowBound=0.0)

        eta = opt_input.round_trip_efficiency ** 0.5
        initial_soc = opt_input.battery_capacity_kwh * opt_input.initial_soc_ratio

        # Objective Function: Energy Cost + Peak Surcharge Component
        energy_cost = pulp.lpSum([
            grid_kw[t] * opt_input.grid_tariff_lkr_kwh[t] * dt for t in range(T)
        ])
        peak_surcharge = peak_grid * (opt_input.peak_demand_penalty_lkr_kva / 30.0)
        prob += energy_cost + peak_surcharge

        # Constraints
        for t in range(T):
            # 1. Power Balance: Grid + Solar + Discharge >= BaseLoad + Charge
            prob += (grid_kw[t] + opt_input.solar_gen_kw[t] + discharge_kw[t] >= opt_input.base_load_kw[t] + charge_kw[t]), f"Power_Balance_{t}"

            # 2. Peak Demand tracking
            prob += (peak_grid >= grid_kw[t]), f"Peak_Tracking_{t}"

            # 3. SOC Continuity
            prev_soc = initial_soc if t == 0 else soc_kwh[t - 1]
            prob += (soc_kwh[t] == prev_soc + (charge_kw[t] * eta - discharge_kw[t] / eta) * dt), f"SOC_Continuity_{t}"

        # Solve silently
        solver = pulp.PULP_CBC_CMD(msg=False)
        status = prob.solve(solver)

        if pulp.LpStatus[status] != "Optimal":
            raise InfeasibleOptimizationError(
                message=f"MILP solver terminated with non-optimal status: {pulp.LpStatus[status]}",
                details={"solver_status": pulp.LpStatus[status]}
            )

        # Extract values
        res_grid = [round(float(pulp.value(grid_kw[t])), 2) for t in range(T)]
        res_charge = [round(float(pulp.value(charge_kw[t])), 2) for t in range(T)]
        res_discharge = [round(float(pulp.value(discharge_kw[t])), 2) for t in range(T)]
        res_soc = [round(float(pulp.value(soc_kwh[t])), 2) for t in range(T)]

        opt_cost = sum(res_grid[t] * opt_input.grid_tariff_lkr_kwh[t] * dt for t in range(T))
        baseline_cost = sum(
            max(0.0, opt_input.base_load_kw[t] - opt_input.solar_gen_kw[t]) * opt_input.grid_tariff_lkr_kwh[t] * dt
            for t in range(T)
        )

        net_savings = max(0.0, baseline_cost - opt_cost)
        savings_pct = (net_savings / baseline_cost * 100.0) if baseline_cost > 0 else 0.0

        peak_base = max(max(0.0, opt_input.base_load_kw[t] - opt_input.solar_gen_kw[t]) for t in range(T))
        peak_opt = max(res_grid)

        solve_duration = (time.time() - start_time) * 1000.0

        # Identify binding constraints
        binding = []
        for t in range(T):
            if res_discharge[t] >= opt_input.max_discharge_rate_kw - 0.5:
                binding.append(BindingConstraint(
                    name="Max Discharge Rate",
                    time_slot=opt_input.time_slots[t],
                    threshold=opt_input.max_discharge_rate_kw,
                    actual_value=res_discharge[t]
                ))

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
            peak_demand_baseline_kw=round(peak_base, 1),
            peak_demand_optimized_kw=round(peak_opt, 1),
            solver_status="Optimal",
            solve_time_ms=solve_duration,
            binding_constraints=binding[:5]
        )
