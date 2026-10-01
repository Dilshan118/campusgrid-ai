"""
CampusGrid AI: Agent 4 — Fairness Tier Guardrails

Three pieces, all deterministic and free of I/O:
1. classify_room_type() — which fairness tier a room category belongs to.
2. TierPolicy / TierLoads / synthetic_tier_loads() — the per-tier load profile and the rules the
   MILP solver enforces for it (milp_solver.py builds the constraints).
3. allocate_to_zones() — splits a tier's curtailment across the zones in that tier in
   proportion to each zone's load, so every zone in a tier gives up the same percentage and a
   zone's label (dormitory, office, ...) cannot change what it is asked to give up.

Tier rules (guide section 2.3, decisions D-1 to D-3):
- Tier 0 is never curtailed. Its load is always served in full; if the grid limit makes that
  impossible, the solver raises InfeasibleOptimizationError rather than under-serve it.
- Tier 1 may reduce cooling by up to `tier1_max_flex_c` degrees' worth of power during peak-tariff
  intervals, and the energy is paid back later the same day (the room is re-cooled). The kW per
  degree comes from the digital twin (WIRE-3); without it Tier 1 is not flexed at all.
- Tier 2 may be shifted to other intervals; every kWh moved is recovered within the same
  48-interval day (D-3), never dropped.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from src.agents.dispatch_explanation.tier_category_mapping import (
    CATEGORY_TIER_MAP,
    SYNTHETIC_TIER_SHARES,
    TIER_0,
    TIER_1,
    TIER_2,
)
from src.domain.exceptions.base import DomainException, EntityNotFoundError

# Allowed gap (kW) between the tier loads' sum and the campus load they must add up to.
_SPLIT_TOLERANCE_KW = 0.5


def classify_room_type(room_type: str) -> str:
    """
    Resolves a room category string to its fairness tier via an exact,
    case-sensitive match against CATEGORY_TIER_MAP.

    Raises EntityNotFoundError if room_type is not listed (including empty/blank
    input) — unclassifiable input must be rejected, never silently defaulted to a tier.
    """
    tier = CATEGORY_TIER_MAP.get(room_type)
    if tier is None:
        raise EntityNotFoundError(entity_type="RoomCategoryTier", identifier=room_type)
    return tier


@dataclass(frozen=True)
class TierPolicy:
    """Solver-side fairness rules. Defaults are the guide's policy."""
    tier1_max_flex_c: float = 1.5
    # kW of cooling saved per degree of Tier 1 setback (WIRE-3, from Agent 2). None -> no Tier 1 flex.
    tier1_kw_per_degree_c: Optional[float] = None
    # A shifted Tier 2 interval may run at most this multiple of its own peak load.
    tier2_max_rebound_ratio: float = 2.0
    # Small LKR/kWh costs so load is only moved when it actually saves money; not part of the
    # reported bill. Tier 1 costs more to move than Tier 2 because people feel it.
    tier1_flex_cost_lkr_kwh: float = 2.0
    tier2_shift_cost_lkr_kwh: float = 0.5

    def __post_init__(self):
        if not 0.0 <= self.tier1_max_flex_c <= 1.5:
            raise DomainException("Tier 1 flexibility must be between 0 and 1.5 C.", error_code="TIER_POLICY_INVALID")
        if self.tier1_kw_per_degree_c is not None and self.tier1_kw_per_degree_c < 0:
            raise DomainException("Tier 1 kW per degree cannot be negative.", error_code="TIER_POLICY_INVALID")
        if self.tier2_max_rebound_ratio < 1.0:
            raise DomainException("Tier 2 rebound ratio must be at least 1.", error_code="TIER_POLICY_INVALID")


@dataclass(frozen=True)
class TierLoads:
    """Per-interval load of each tier (kW). Must add up to the campus load."""
    tier0_kw: List[float]
    tier1_kw: List[float]
    tier2_kw: List[float]
    source: str  # "synthetic" or "metered"

    def validate_against(self, base_load_kw: Sequence[float]) -> None:
        n = len(base_load_kw)
        for name, series in (("tier0", self.tier0_kw), ("tier1", self.tier1_kw), ("tier2", self.tier2_kw)):
            if len(series) != n:
                raise DomainException(
                    f"{name} load has {len(series)} values, the campus load has {n}.",
                    error_code="TIER_LOAD_INVALID",
                )
            # NaN compares False with everything, so without the finiteness check a NaN series
            # passed both the sign and the sum checks below (SEC-06).
            if any(not math.isfinite(v) for v in series):
                raise DomainException(f"{name} load contains a non-finite value.", error_code="TIER_LOAD_INVALID")
            if any(v < 0 for v in series):
                raise DomainException(f"{name} load contains a negative value.", error_code="TIER_LOAD_INVALID")
        for t in range(n):
            total = self.tier0_kw[t] + self.tier1_kw[t] + self.tier2_kw[t]
            if abs(total - base_load_kw[t]) > _SPLIT_TOLERANCE_KW:
                raise DomainException(
                    f"Tier loads add up to {total:.1f} kW at interval {t}, but the campus load is {base_load_kw[t]:.1f} kW.",
                    error_code="TIER_LOAD_INVALID",
                )


def synthetic_tier_loads(base_load_kw: Sequence[float], shares: Optional[Dict[str, float]] = None) -> TierLoads:
    """D-1: split the campus forecast into tiers by fixed shares. Labelled synthetic."""
    shares = shares or SYNTHETIC_TIER_SHARES
    if set(shares) != {TIER_0, TIER_1, TIER_2} or abs(sum(shares.values()) - 1.0) > 1e-6 or min(shares.values()) < 0:
        raise DomainException("Tier shares must cover TIER_0, TIER_1 and TIER_2 and add up to 1.", error_code="TIER_LOAD_INVALID")
    t0 = [round(v * shares[TIER_0], 4) for v in base_load_kw]
    t2 = [round(v * shares[TIER_2], 4) for v in base_load_kw]
    t1 = [round(v - a - b, 4) for v, a, b in zip(base_load_kw, t0, t2)]  # remainder, so the sum is exact
    return TierLoads(tier0_kw=t0, tier1_kw=t1, tier2_kw=t2, source="synthetic")


def allocate_to_zones(tier_reduction_kw: float, zone_loads_kw: Dict[str, float]) -> Dict[str, float]:
    """
    Splits one interval's tier-level reduction across that tier's zones in proportion to load.

    Every zone gives up the same fraction of its own load, and the result depends only on the
    loads — swapping two zones' names swaps their allocations and changes nothing else.
    """
    if tier_reduction_kw < 0:
        raise DomainException("A reduction cannot be negative.", error_code="TIER_LOAD_INVALID")
    if any(v < 0 for v in zone_loads_kw.values()):
        raise DomainException("A zone load cannot be negative.", error_code="TIER_LOAD_INVALID")
    total = sum(zone_loads_kw.values())
    if total <= 0:
        if tier_reduction_kw > 0:
            raise DomainException("Cannot reduce a tier that has no load.", error_code="TIER_LOAD_INVALID")
        return {zone: 0.0 for zone in zone_loads_kw}
    if tier_reduction_kw > total + 1e-9:
        raise DomainException("The reduction exceeds the tier's load.", error_code="TIER_LOAD_INVALID")
    fraction = tier_reduction_kw / total
    return {zone: load * fraction for zone, load in zone_loads_kw.items()}
