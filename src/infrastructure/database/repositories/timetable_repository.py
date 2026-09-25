"""
CampusGrid AI: Timetable Repository Implementations
Adapters for lecture schedules and expected classroom occupancy.

OWNER: Member 2 (Developer 1 - Telemetry & Machine Learning)

InMemoryTimetableRepository serves the seed teaching day; PostgresTimetableRepository reads the
`timetables` table in backend/data/init.sql (selected by DATABASE_PROVIDER=postgres) and falls
back to the seed day when the table has no rows for the requested weekday.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy import text
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


class PostgresTimetableRepository(TimetableRepository):
    """
    PostgreSQL implementation of TimetableRepository, backed by the `timetables`
    table in `backend/data/init.sql`. `start_time`/`end_time` are stored as SQL
    TIME columns; comparisons against `time_slot` ("HH:MM") work directly because
    Postgres TIME's string form is lexically comparable to zero-padded HH:MM.
    """

    def __init__(self, engine, fallback: Optional[TimetableRepository] = None):
        self.engine = engine
        self._fallback = fallback or InMemoryTimetableRepository()

    def get_schedule_for_day(self, day_of_week: int) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT schedule_id, room_id, course_code, day_of_week, "
                    "start_time, end_time, expected_students "
                    "FROM timetables WHERE day_of_week = :dow ORDER BY start_time;"
                ),
                {"dow": day_of_week}
            ).fetchall()

        if not rows:
            return self._fallback.get_schedule_for_day(day_of_week)

        return [
            {
                "schedule_id": r[0],
                "room_id": r[1],
                "course_code": r[2],
                "day_of_week": r[3],
                "start_time": str(r[4])[:5],
                "end_time": str(r[5])[:5],
                "expected_students": r[6],
            }
            for r in rows
        ]

    def get_room_occupancy(self, room_id: str, time_slot: str, day_of_week: int) -> int:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT expected_students FROM timetables "
                    "WHERE room_id = :room AND day_of_week = :dow "
                    "AND start_time <= :slot AND end_time >= :slot "
                    "LIMIT 1;"
                ),
                {"room": room_id, "dow": day_of_week, "slot": time_slot}
            ).fetchone()
        if row is not None:
            return int(row[0])
        return 0
