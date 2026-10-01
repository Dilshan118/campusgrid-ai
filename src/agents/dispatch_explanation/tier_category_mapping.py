"""
CampusGrid AI: Agent 4 — Room-Category-to-Tier Mapping Data
Source of authority: TEAM_GUIDES/MEMBER_4_OPTIMIZATION_AND_RESPONSIBLE_AI_GUIDE.md, section 2.3,
plus team decision D-2 (docs/TEAM_LEAD_REVIEW_AND_INTEGRATION_REPORT.md, section 6).

This is a plain data file — CATEGORY -> TIER, and the synthetic campus load split used when no
per-tier metering exists (decision D-1). It does not map individual room_id values: the room
repository (owned by Member 1) carries a room_type string, which tier_guardrails resolves here.

Categories not listed are rejected by tier_guardrails.classify_room_type() rather than
defaulted to a tier, so an unknown facility can never silently become curtailable.
"""

# Tier identifiers, referenced by CATEGORY_TIER_MAP below.
TIER_0 = "TIER_0"  # Never curtailed — hard mathematical constraint
TIER_1 = "TIER_1"  # May flex +/-1.5 C during peak hours
TIER_2 = "TIER_2"  # Fully curtailable, shift to cheap hours

TIER_DESCRIPTIONS = {
    TIER_0: "critical (research labs, medical rooms, server rooms): never curtailed",
    TIER_1: "comfort-flexible (teaching, study, office and residential spaces): up to 1.5 C during peak hours",
    TIER_2: "shiftable (EV chargers, pumps, ornamental lighting): moved to cheaper hours, recovered the same day",
}

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
    # D-2: teaching spaces in the room inventory join Tier 1.
    "Auditorium": TIER_1,
    "Computer Lab": TIER_1,
    # Residential space sits in the same tier as offices, so student housing can never be
    # treated as more curtailable than administration (Student 3 fairness requirement).
    "Dormitory": TIER_1,

    # Tier 2 — EV chargers, pumps, ornamental lighting
    "EV Charger": TIER_2,
    "Pump": TIER_2,
    "Ornamental Lighting": TIER_2,
}

# D-1: no sub-metering exists, so per-tier load is a SYNTHETIC, documented share of the campus
# forecast. These shares are an assumption, not telemetry — every plan that uses them says so.
SYNTHETIC_TIER_SHARES = {
    TIER_0: 0.10,
    TIER_1: 0.80,
    TIER_2: 0.10,
}
