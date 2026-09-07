"""
CampusGrid AI: Timetable Repository Implementations
Adapters for lecture schedules and expected classroom occupancy.

OWNER: Member 2 (Developer 1 - Telemetry & Machine Learning)

A PostgresTimetableRepository does not exist yet, so the DI container falls back to
the in-memory seed even when DATABASE_PROVIDER=postgres. Adding it is Developer 1's
task; the `timetables` table it should read is already defined in backend/data/init.sql.
"""

from typing import List, Dict, Any
from src.domain.interfaces.repositories import TimetableRepository


class InMemoryTimetableRepository(TimetableRepository):
    """In-memory academic timetable seeded with a benchmark teaching day."""

    def __init__(self):
        self._schedules = [
            {"schedule_id": 1, "room_id": "LH-1", "course_code": "IT3041", "day_of_week": 1,
             "start_time": "08:30", "end_time": "11:30", "expected_students": 220},
            {"schedule_id": 2, "room_id": "LH-1", "course_code": "IT3020", "day_of_week": 1,
             "start_time": "13:00", "end_time": "16:00", "expected_students": 240},
            {"schedule_id": 3, "room_id": "AUD-1", "course_code": "EN1010", "day_of_week": 1,
             "start_time": "09:00", "end_time": "12:00", "expected_students": 550},
        ]

    def get_schedule_for_day(self, day_of_week: int) -> List[Dict[str, Any]]:
        return [s for s in self._schedules if s["day_of_week"] == day_of_week]

    def get_room_occupancy(self, room_id: str, time_slot: str, day_of_week: int) -> int:
        for s in self._schedules:
            if s["room_id"] == room_id and s["day_of_week"] == day_of_week:
                if s["start_time"] <= time_slot <= s["end_time"]:
                    return s["expected_students"]
        return 0
