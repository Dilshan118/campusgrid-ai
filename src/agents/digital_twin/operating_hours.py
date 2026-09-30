"""
CampusGrid AI: Agent 2 — Campus Operating Hours
Module Owner: Member 3 (Digital Twin, Cyber-Physical Physics & Simulation)

When a room is in use decides three things in a what-if simulation: when people are in it
(occupant heat), when its air conditioning runs, and which half-hours count towards the
comfort check — an empty room drifting warm at 3 a.m. is not a comfort violation.

Campus policy: weekdays 08:30-17:30, weekends 08:00-20:00.
"""

from dataclasses import dataclass
from datetime import date
from typing import Dict, List

from src.shared.datetime_utils import time_slot_to_index

WEEKDAY_HOURS = ("08:30", "17:30")
WEEKEND_HOURS = ("08:00", "20:00")


@dataclass(frozen=True)
class OperatingHours:
    day_type: str  # "weekday" or "weekend"
    start: str     # "HH:MM", inclusive
    end: str       # "HH:MM", exclusive

    def as_dict(self) -> Dict[str, str]:
        return {"day_type": self.day_type, "start": self.start, "end": self.end}


def operating_hours_for(day: date) -> OperatingHours:
    if day.weekday() >= 5:  # Saturday, Sunday
        return OperatingHours("weekend", *WEEKEND_HOURS)
    return OperatingHours("weekday", *WEEKDAY_HOURS)


def occupied_mask(hours: OperatingHours, n_intervals: int = 48) -> List[bool]:
    """True for every half-hour slot that starts inside the operating window."""
    start_idx = time_slot_to_index(hours.start)
    end_idx = time_slot_to_index(hours.end)
    return [start_idx <= i < end_idx for i in range(n_intervals)]


def describe_operating_hours() -> Dict[str, Dict[str, str]]:
    return {
        "weekday": {"start": WEEKDAY_HOURS[0], "end": WEEKDAY_HOURS[1]},
        "weekend": {"start": WEEKEND_HOURS[0], "end": WEEKEND_HOURS[1]},
    }
