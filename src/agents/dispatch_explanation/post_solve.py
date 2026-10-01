"""
CampusGrid AI: Agent 4 — Post-Solve Arithmetic Check
Module Owner: Member 4 (Operations Research, Linear Optimization & Responsible AI)

Re-checks a solved schedule against every constraint using only the numbers the solver
returned (rounded to 0.01, as the reviewer sees them), independently of PuLP. A plan that
fails here is never shown: the solver raises instead. This is the arithmetic half of
post-solve validation; the physical half (comfort and battery simulated by the digital twin)
is DigitalTwinAgent.verify_dispatch_plan().
"""

from typing import Any, Dict, List, Optional
from src.domain.entities.optimization import OptimizationInput

# The solver rounds each value to 0.01, so equalities can drift by a few hundredths.
_KW_TOLERANCE = 0.1
_KWH_STEP_TOLERANCE = 0.05
_ENERGY_TOLERANCE_KWH = 0.5


def check_solution(
    opt_input: OptimizationInput,
    tiers: Optional[List[List[float]]],
    grid: List[float],
    charge: List[float],
    discharge: List[float],
    soc: List[float],
    served_t1: Optional[List[float]],
    served_t2: Optional[List[float]],
    eta: float,
    dt: float,
) -> Dict[str, Any]:
    T = len(grid)
    failures: List[str] = []

    def fail(name: str, intervals: List[int]):
        if intervals:
            slots = ", ".join(opt_input.time_slots[i] for i in intervals[:5])
            failures.append(f"{name} at {slots}" + (f" and {len(intervals) - 5} more" if len(intervals) > 5 else ""))

    if tiers is None:
        served = list(opt_input.base_load_kw)
    else:
        t0, t1, t2 = tiers
        served = [t0[i] + served_t1[i] + served_t2[i] for i in range(T)]
        r = opt_input.tier1_max_reduction_ratio
        fail("Tier 1 outside its flexibility band",
             [i for i in range(T) if not (t1[i] * (1 - r) - _KW_TOLERANCE <= served_t1[i] <= t1[i] * (1 + r) + _KW_TOLERANCE)])
        if abs(sum(served_t1) - sum(t1)) * dt > _ENERGY_TOLERANCE_KWH:
            failures.append("Tier 1 daily energy changed (air-conditioning energy must be shifted, not cut)")
        cap = opt_input.tier2_max_kw or max(t2, default=0.0)
        fail("Tier 2 above its rated power",
             [i for i in range(T) if served_t2[i] > max(cap, t2[i]) + _KW_TOLERANCE or served_t2[i] < -_KW_TOLERANCE])
        if abs(sum(served_t2) - sum(t2)) * dt > _ENERGY_TOLERANCE_KWH:
            failures.append("Tier 2 daily energy changed")

    fail("Supply below demand",
         [i for i in range(T) if grid[i] + opt_input.solar_gen_kw[i] + discharge[i] < served[i] + charge[i] - _KW_TOLERANCE])
    fail("Charging above the rated limit", [i for i in range(T) if charge[i] > opt_input.max_charge_rate_kw + _KW_TOLERANCE])
    fail("Discharging above the rated limit", [i for i in range(T) if discharge[i] > opt_input.max_discharge_rate_kw + _KW_TOLERANCE])
    fail("Charging and discharging at once", [i for i in range(T) if charge[i] > _KW_TOLERANCE and discharge[i] > _KW_TOLERANCE])
    if opt_input.max_grid_import_kw is not None:
        fail("Grid import above the limit", [i for i in range(T) if grid[i] > opt_input.max_grid_import_kw + _KW_TOLERANCE])

    capacity = opt_input.battery_capacity_kwh
    low, high = capacity * opt_input.min_soc_ratio, capacity * opt_input.max_soc_ratio
    fail("State of charge outside its band", [i for i in range(T) if not (low - _KW_TOLERANCE <= soc[i] <= high + _KW_TOLERANCE)])
    initial = capacity * opt_input.initial_soc_ratio
    fail("State of charge does not follow the charge/discharge schedule", [
        i for i in range(T)
        if abs(soc[i] - ((initial if i == 0 else soc[i - 1]) + (charge[i] * eta - discharge[i] / eta) * dt)) > _KWH_STEP_TOLERANCE
    ])
    if T and soc[-1] < initial - _ENERGY_TOLERANCE_KWH:
        failures.append("Battery ends the day below its starting charge")

    return {
        "passed": not failures,
        "failures": failures,
        "tier0_curtailed_kw": 0.0 if tiers is not None else None,  # Tier 0 has no decision variable
        "checked_intervals": T,
    }
