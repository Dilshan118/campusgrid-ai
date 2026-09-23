"""
Unit tests for Member 4 (Agent 4: Room Tier Classification).
Terminal Command to run:
    pytest tests/unit/test_member4_tier_guardrails.py -v
"""

import pytest
from src.agents.dispatch_explanation.tier_guardrails import classify_room_type
from src.agents.dispatch_explanation.tier_category_mapping import TIER_0, TIER_1, TIER_2
from src.domain.exceptions.base import EntityNotFoundError


@pytest.mark.parametrize(
    "room_type, expected_tier",
    [
        ("Research Lab", TIER_0),
        ("Medical Room", TIER_0),
        ("Server Room", TIER_0),
        ("Lecture Hall", TIER_1),
        ("Library", TIER_1),
        ("Office", TIER_1),
        ("EV Charger", TIER_2),
        ("Pump", TIER_2),
        ("Ornamental Lighting", TIER_2),
    ],
)
def test_classify_room_type_supported_categories(room_type, expected_tier):
    assert classify_room_type(room_type) == expected_tier


@pytest.mark.parametrize(
    "room_type",
    [
        "Computer Lab",
        "Auditorium",
        "Dormitory",
        "Laboratory",
        "",
    ],
)
def test_classify_room_type_rejects_unsupported_categories(room_type):
    with pytest.raises(EntityNotFoundError):
        classify_room_type(room_type)
