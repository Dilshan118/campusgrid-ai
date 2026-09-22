"""
CampusGrid AI: Agent 4 — Room Tier Classification
Classification-only layer over tier_category_mapping.CATEGORY_TIER_MAP.

This module answers "which fairness tier does this room category belong to?"
and nothing else. It does NOT enforce Tier 0 non-curtailment, Tier 1 thermal
flexibility, or Tier 2 curtailment, and it does NOT touch the MILP solver,
OptimizationInput/OptimizationResult, or the room repository. Those are
separate, later increments — see TEAM_GUIDES/MEMBER_4_OPTIMIZATION_AND_
RESPONSIBLE_AI_GUIDE.md section 2.3.
"""

from src.agents.dispatch_explanation.tier_category_mapping import CATEGORY_TIER_MAP
from src.domain.exceptions.base import EntityNotFoundError


def classify_room_type(room_type: str) -> str:
    """
    Resolves a room category string to its fairness tier via an exact,
    case-sensitive match against CATEGORY_TIER_MAP.

    Deterministic and pure: no database access, file I/O, LLM calls,
    randomness, or network access.

    Raises EntityNotFoundError if room_type is not an exact match for a
    category named in the authoritative guide (this includes unsupported
    categories such as "Computer Lab" or "Auditorium", and empty/blank
    input) — unclassifiable input must be rejected, never silently
    defaulted to a tier.
    """
    tier = CATEGORY_TIER_MAP.get(room_type)
    if tier is None:
        raise EntityNotFoundError(entity_type="RoomCategoryTier", identifier=room_type)
    return tier
