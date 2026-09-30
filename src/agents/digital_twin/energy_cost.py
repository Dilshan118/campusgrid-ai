"""
CampusGrid AI: Agent 2 — Air-Conditioning Energy & Cost Estimate
Module Owner: Member 3 (Digital Twin, Cyber-Physical Physics & Simulation)

Turns a simulated cooling schedule into what the facility manager actually pays: the
electricity the ACs draw (cooling / COP), priced at the PUCSL GP-2 time-of-use reference
rates, plus the room's peak electrical draw — the number that feeds the campus's
maximum-demand charge. Reference rates, not Agent 3's retrieved ones: a what-if
simulation is exploratory and must not depend on a live document search.
"""

from typing import Any, Dict, List

from src.shared.constants import TARIFF_DAY_LKR, TARIFF_OFF_PEAK_LKR, TARIFF_PEAK_LKR
from src.shared.datetime_utils import build_tou_tariff_profile, index_to_time_slot, is_peak_hour

# Coefficient of performance of a typical inverter split unit in a tropical climate:
# 3.2 kW of heat removed per kW of electricity drawn. An engineering estimate.
AC_COP = 3.2


def estimate_hvac_energy(
    cooling_kw: List[float],
    dt_hours: float = 0.5,
    cop: float = AC_COP,
) -> Dict[str, Any]:
    slots = [index_to_time_slot(i) for i in range(len(cooling_kw))]
    tariffs = build_tou_tariff_profile(slots, TARIFF_PEAK_LKR, TARIFF_DAY_LKR, TARIFF_OFF_PEAK_LKR)
    electric_kw = [max(0.0, q) / cop for q in cooling_kw]
    energy_kwh = [kw * dt_hours for kw in electric_kw]

    peak_kw = max(electric_kw, default=0.0)
    peak_slot = slots[electric_kw.index(peak_kw)] if peak_kw > 0 else None
    return {
        "electricity_kwh": round(sum(energy_kwh), 2),
        "cost_lkr": round(sum(kwh * rate for kwh, rate in zip(energy_kwh, tariffs)), 2),
        "peak_electric_kw": round(peak_kw, 2),
        "peak_time": peak_slot,
        "peak_in_tariff_peak_window": bool(peak_slot and is_peak_hour(peak_slot)),
        "cop": cop,
        "tariff_basis": f"PUCSL GP-2 reference rates: LKR {TARIFF_OFF_PEAK_LKR:g} off-peak, "
                        f"{TARIFF_DAY_LKR:g} day, {TARIFF_PEAK_LKR:g} peak per kWh",
    }
