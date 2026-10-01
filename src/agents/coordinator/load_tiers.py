"""
CampusGrid AI: Load-Tier Split for the Dispatch Optimizer
Turns Agent 1's campus demand forecast into the three fairness tiers Agent 4 enforces:

    Tier 0  critical (labs, server rooms, medical, lighting)   never curtailed
    Tier 1  air-conditioning                                    may be pre-cooled / deferred, same daily energy
    Tier 2  shiftable equipment (pumps, EV chargers)            may run at any time, same daily energy

The campus has no sub-metering, so Tier 1 is an assumed share of demand (settings) and Tier 2
is what the planner enters on the dispatch form. Everything not in Tier 1 or 2 is treated as
Tier 0, which errs on the side of never touching a load that might be critical.
"""

from typing import Any, Dict, List, Optional


def _slot_index(time_slots: List[str], hhmm: str) -> int:
    return time_slots.index(hhmm) if hhmm in time_slots else 0


def build_tier_profiles(
    demand_kw: List[float],
    time_slots: List[str],
    hvac_share: float,
    shiftable_kw: float = 0.0,
    shiftable_hours: float = 0.0,
    shiftable_start: str = "08:00",
) -> Optional[Dict[str, Any]]:
    """{tier0_load_kw, tier1_load_kw, tier2_load_kw, notes} or None when nothing is flexible."""
    if hvac_share <= 0 and (shiftable_kw <= 0 or shiftable_hours <= 0):
        return None
    T = len(demand_kw)
    tier1 = [round(d * hvac_share, 3) for d in demand_kw]

    # Tier 2 sits where it usually runs (from the usual start, wrapping past midnight), never
    # above what is left of the forecast after air-conditioning.
    tier2 = [0.0] * T
    n_slots = int(round(shiftable_hours * 2)) if shiftable_kw > 0 else 0
    start = _slot_index(time_slots, shiftable_start)
    for k in range(min(n_slots, T)):
        i = (start + k) % T
        tier2[i] = round(min(shiftable_kw, max(0.0, demand_kw[i] - tier1[i])), 3)

    tier0 = [round(demand_kw[i] - tier1[i] - tier2[i], 3) for i in range(T)]
    notes = []
    if hvac_share > 0:
        notes.append(
            f"Air-conditioning is assumed to be {hvac_share * 100:.0f}% of campus demand (no sub-metering); "
            "the rest of the forecast is treated as critical Tier 0 load that is never curtailed."
        )
    if n_slots:
        clipped = sum(1 for i in range(T) if 0 < tier2[i] < shiftable_kw)
        notes.append(
            f"Shiftable equipment: {shiftable_kw:g} kW for {shiftable_hours:g} h, normally from {shiftable_start}"
            + (f" (limited by the forecast in {clipped} half-hour(s))." if clipped else ".")
        )
    return {"tier0_load_kw": tier0, "tier1_load_kw": tier1, "tier2_load_kw": tier2, "notes": notes}


def scaled_hvac_schedule(room_hvac_kw: List[float], tier1_planned: List[float], tier1_served: List[float]) -> List[float]:
    """The room's thermostat cooling schedule scaled by how much the plan moved campus air-conditioning
    in each half-hour — what the digital twin must re-simulate to check the plan keeps the room comfortable."""
    return [
        round(q * (served / planned), 3) if planned > 0 else q
        for q, planned, served in zip(room_hvac_kw, tier1_planned, tier1_served)
    ]
