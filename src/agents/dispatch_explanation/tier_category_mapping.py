"""
CampusGrid AI: Agent 4 — Room-Category-to-Tier Mapping Data
Source of authority: TEAM_GUIDES/MEMBER_4_OPTIMIZATION_AND_RESPONSIBLE_AI_GUIDE.md, section 2.3.

This is a plain data file — CATEGORY -> TIER only. It intentionally does not map
individual room_id values, because the room repository (src/infrastructure/database/
repositories/room_repository.py, owned by Member 1) does not carry an authoritative
tier assignment; a future classifier is expected to resolve a room's own room_type
string against this table.

Only categories explicitly named in the authoritative guide are listed. A category
observed in real seed data but not named by the guide (e.g. "Auditorium", "Computer
Lab") or mentioned only in fairness-test scenario language rather than the tier table
(e.g. "Dormitory") is deliberately omitted rather than guessed — see the team's own
audit notes before adding to this file.

Not yet imported by any agent, solver, or test. Wiring and classification logic are
separate, later increments.
"""

# Tier identifiers, referenced by CATEGORY_TIER_MAP below.
TIER_0 = "TIER_0"  # Never curtailed — hard mathematical constraint
TIER_1 = "TIER_1"  # May flex +/-1.5 C during peak hours
TIER_2 = "TIER_2"  # Fully curtailable, shift to cheap hours

# Category -> Tier, using the guide's own facility terminology verbatim.
CATEGORY_TIER_MAP = {
    # Tier 0 — Research labs, medical rooms, server rooms
    "Research Lab": TIER_0,
    "Medical Room": TIER_0,
    "Server Room": TIER_0,

    # Tier 1 — Lecture halls, libraries, offices
    "Lecture Hall": TIER_1,
    "Library": TIER_1,
    "Office": TIER_1,

    # Tier 2 — EV chargers, pumps, ornamental lighting
    "EV Charger": TIER_2,
    "Pump": TIER_2,
    "Ornamental Lighting": TIER_2,
}
