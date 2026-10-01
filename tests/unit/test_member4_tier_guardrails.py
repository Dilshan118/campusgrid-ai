"""
Unit tests for Member 4 (Agent 4: Room Tier Classification and Fairness Guardrails).
Terminal Command to run:
    pytest tests/unit/test_member4_tier_guardrails.py -v
"""

import pytest
from src.agents.dispatch_explanation.tier_guardrails import (
    TierPolicy,
    allocate_to_zones,
    classify_room_type,
    synthetic_tier_loads,
)
from src.agents.dispatch_explanation.tier_category_mapping import TIER_0, TIER_1, TIER_2
from src.domain.exceptions.base import DomainException, EntityNotFoundError


@pytest.mark.parametrize(
    "room_type, expected_tier",
    [
        ("Research Lab", TIER_0),
        ("Medical Room", TIER_0),
        ("Server Room", TIER_0),
        ("Lecture Hall", TIER_1),
        ("Library", TIER_1),
        ("Office", TIER_1),
        ("Auditorium", TIER_1),      # decision D-2
        ("Computer Lab", TIER_1),    # decision D-2
        ("Dormitory", TIER_1),       # same tier as offices
        ("EV Charger", TIER_2),
        ("Pump", TIER_2),
        ("Ornamental Lighting", TIER_2),
    ],
)
def test_classify_room_type_supported_categories(room_type, expected_tier):
    assert classify_room_type(room_type) == expected_tier


@pytest.mark.parametrize("room_type", ["Laboratory", "Legacy Chiller Plant", "server room", "", " "])
def test_classify_room_type_rejects_unsupported_categories(room_type):
    with pytest.raises(EntityNotFoundError):
        classify_room_type(room_type)


def test_synthetic_split_adds_up_exactly_and_is_labelled():
    load = [100.0, 333.3, 0.0, 812.7]
    loads = synthetic_tier_loads(load)
    assert loads.source == "synthetic"
    for t, total in enumerate(load):
        assert loads.tier0_kw[t] + loads.tier1_kw[t] + loads.tier2_kw[t] == pytest.approx(total, abs=1e-6)
    loads.validate_against(load)


def test_synthetic_split_rejects_shares_that_do_not_add_up():
    with pytest.raises(DomainException):
        synthetic_tier_loads([100.0], {TIER_0: 0.5, TIER_1: 0.5, TIER_2: 0.5})


def test_allocation_is_proportional_to_load():
    cut = allocate_to_zones(30.0, {"A": 100.0, "B": 200.0})
    assert cut == pytest.approx({"A": 10.0, "B": 20.0})
    assert cut["A"] / 100.0 == pytest.approx(cut["B"] / 200.0)


def test_allocation_does_not_depend_on_zone_names():
    before = allocate_to_zones(24.0, {"Dormitory Block A": 80.0, "Admin Office": 80.0})
    after = allocate_to_zones(24.0, {"Admin Office": 80.0, "Dormitory Block A": 80.0})
    assert before == after
    assert before["Dormitory Block A"] == before["Admin Office"]


@pytest.mark.parametrize("reduction, zones", [(-1.0, {"A": 10.0}), (50.0, {"A": 10.0}), (5.0, {"A": 0.0})])
def test_allocation_rejects_impossible_requests(reduction, zones):
    with pytest.raises(DomainException):
        allocate_to_zones(reduction, zones)


def test_tier_policy_rejects_more_than_the_guide_allows():
    with pytest.raises(DomainException):
        TierPolicy(tier1_max_flex_c=3.0)
    with pytest.raises(DomainException):
        TierPolicy(tier1_kw_per_degree_c=-1.0)
