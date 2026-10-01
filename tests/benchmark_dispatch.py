"""Fixed synthetic 48-interval comparison of the current and reference MILP solvers."""

import json
from pathlib import Path

from src.agents.dispatch_explanation.milp_solver import CampusMicrogridOptimizer
from src.domain.entities.optimization import OptimizationInput
from src.infrastructure.reference_baselines.baseline_milp import BaselineCampusMicrogridOptimizer


def main():
    slots = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]
    demand = [300.0 + (350.0 if 8 <= h <= 17 else 0.0) + (150.0 if 18 <= h < 22 else 0.0)
              for h in range(24) for _ in (0, 30)]
    solar = [200.0 if 9 <= h <= 15 else 0.0 for h in range(24) for _ in (0, 30)]
    tariffs = [26.60 if ((h == 18 and m == 30) or 19 <= h < 22 or (h == 22 and m == 0))
               else (15.40 if h < 5 or (h == 5 and m == 0) or (h == 22 and m == 30) or h >= 23 else 21.80)
               for h in range(24) for m in (0, 30)]
    payload = OptimizationInput(time_slots=slots, base_load_kw=demand, solar_gen_kw=solar,
                                grid_tariff_lkr_kwh=tariffs, battery_capacity_kwh=500.0,
                                max_charge_rate_kw=100.0, max_discharge_rate_kw=100.0)
    results = {}
    common_penalty = payload.peak_demand_penalty_lkr_kva / 30.0
    for name, solver in (("current", CampusMicrogridOptimizer()),
                         ("reference", BaselineCampusMicrogridOptimizer())):
        result = solver.solve(payload)
        common_energy = sum(grid * tariff * 0.5 for grid, tariff in
                            zip(result.optimized_grid_kw, payload.grid_tariff_lkr_kwh))
        results[name] = {
            "status": result.solver_status,
            "intervals": len(result.optimized_grid_kw),
            "reported_optimized_cost_lkr": result.optimized_cost_lkr,
            "common_objective_cost_lkr": round(common_energy + max(result.optimized_grid_kw) * common_penalty, 2),
            "reported_baseline_cost_lkr": result.baseline_cost_lkr,
            "reported_peak_grid_kw": result.peak_demand_optimized_kw,
            "soc_min_kwh": min(result.battery_soc_kwh),
            "soc_max_kwh": max(result.battery_soc_kwh),
            "max_charge_kw": max(result.battery_charge_kw),
            "max_discharge_kw": max(result.battery_discharge_kw),
            "solve_time_ms": round(result.solve_time_ms, 3),
        }
    print(json.dumps({"dataset": "fixed synthetic 48-interval demand/solar/tariff profile",
                      "assumptions": {"battery_capacity_kwh": 500, "charge_discharge_limit_kw": 100,
                                      "round_trip_efficiency": 0.92},
                      "solvers": results}, indent=2))


if __name__ == "__main__":
    main()
