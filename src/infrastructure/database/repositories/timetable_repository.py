"""
CampusGrid AI: Timetable Repository Implementations
Adapters for lecture schedules and expected classroom occupancy.

OWNER: Member 2 (Developer 1 - Telemetry & Machine Learning)

InMemoryTimetableRepository serves the seed teaching day until a timetable is uploaded;
PostgresTimetableRepository reads the `timetables` table in backend/data/init.sql (selected by
DATABASE_PROVIDER=postgres) and falls back to the seed day only while that table is empty.

There is no live timetable feed: the faculty's timetable is uploaded as a CSV (or edited one
session at a time) through TimetableService, which validates every row before these adapters
write anything.
"""

import threading
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from src.domain.interfaces.repositories import TimetableRepository

SEED_SCHEDULE: List[Dict[str, Any]] = [
    {"room_id": "LH-1", "course_code": "IT3041", "day_of_week": 1,
     "start_time": "08:30", "end_time": "11:30", "expected_students": 220},
    {"room_id": "LH-1", "course_code": "IT3020", "day_of_week": 1,
     "start_time": "13:00", "end_time": "16:00", "expected_students": 240},
    {"room_id": "AUD-1", "course_code": "EN1010", "day_of_week": 1,
     "start_time": "09:00", "end_time": "12:00", "expected_students": 550},
]


def _occupancy(schedule: List[Dict[str, Any]], room_id: str, time_slot: str) -> int:
    for s in schedule:
        if s["room_id"] == room_id and s["start_time"] <= time_slot <= s["end_time"]:
            return int(s["expected_students"])
    return 0


def _sorted(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(entries, key=lambda e: (e["day_of_week"], e["start_time"], e["room_id"]))


class InMemoryTimetableRepository(TimetableRepository):
    """In-memory academic timetable seeded with a benchmark teaching day."""

    def __init__(self):
        self._lock = threading.Lock()
        self._schedules: List[Dict[str, Any]] = []
        self._next_id = 1
        self._managed = False
        self._insert(SEED_SCHEDULE)

    def _insert(self, entries: List[Dict[str, Any]]) -> List[int]:
        ids = []
        for e in entries:
            self._schedules.append({**e, "schedule_id": self._next_id})
            ids.append(self._next_id)
            self._next_id += 1
        return ids

    def get_schedule_for_day(self, day_of_week: int) -> List[Dict[str, Any]]:
        with self._lock:
            return _sorted([dict(s) for s in self._schedules if s["day_of_week"] == day_of_week])

    def get_room_occupancy(self, room_id: str, time_slot: str, day_of_week: int) -> int:
        return _occupancy(self.get_schedule_for_day(day_of_week), room_id, time_slot)

    def list_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return _sorted([dict(s) for s in self._schedules])

    def replace_all(self, entries: List[Dict[str, Any]]) -> int:
        with self._lock:
            self._schedules = []
            self._insert(entries)
            self._managed = True
            return len(entries)

    def add_entries(self, entries: List[Dict[str, Any]]) -> List[int]:
        with self._lock:
            self._managed = True
            return self._insert(entries)

    def delete_entry(self, schedule_id: int) -> bool:
        with self._lock:
            before = len(self._schedules)
            self._schedules = [s for s in self._schedules if s["schedule_id"] != schedule_id]
            self._managed = True
            return len(self._schedules) < before

    def source(self) -> str:
        return "managed" if self._managed else "seed"


_SELECT = (
    "SELECT schedule_id, room_id, course_code, day_of_week, start_time, end_time, expected_students "
    "FROM timetables"
)


def _row(r) -> Dict[str, Any]:
    return {
        "schedule_id": r[0],
        "room_id": r[1],
        "course_code": r[2],
        "day_of_week": r[3],
        "start_time": str(r[4])[:5],
        "end_time": str(r[5])[:5],
        "expected_students": r[6],
    }


_INSERT = text(
    "INSERT INTO timetables (room_id, course_code, day_of_week, start_time, end_time, expected_students) "
    "VALUES (:room_id, :course_code, :day_of_week, CAST(:start_time AS TIME), CAST(:end_time AS TIME), "
    ":expected_students) RETURNING schedule_id;"
)


class PostgresTimetableRepository(TimetableRepository):
    """
    PostgreSQL implementation of TimetableRepository, backed by the `timetables`
    table in `backend/data/init.sql`. `start_time`/`end_time` are stored as SQL
    TIME columns; comparisons against `time_slot` ("HH:MM") work directly because
    Postgres TIME's string form is lexically comparable to zero-padded HH:MM.

    The seed day is used only while the table is completely empty. Once a timetable exists, a
    weekday without sessions is genuinely empty — it is never filled with the seed Monday.
    """

    def __init__(self, engine, fallback: Optional[TimetableRepository] = None):
        self.engine = engine
        self._fallback = fallback or InMemoryTimetableRepository()

    def _table_empty(self, conn) -> bool:
        return conn.execute(text("SELECT NOT EXISTS (SELECT 1 FROM timetables);")).scalar()

    def get_schedule_for_day(self, day_of_week: int) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(f"{_SELECT} WHERE day_of_week = :dow ORDER BY start_time;"),
                {"dow": day_of_week}
            ).fetchall()
            if not rows and self._table_empty(conn):
                return self._fallback.get_schedule_for_day(day_of_week)
        return [_row(r) for r in rows]

    def get_room_occupancy(self, room_id: str, time_slot: str, day_of_week: int) -> int:
        return _occupancy(self.get_schedule_for_day(day_of_week), room_id, time_slot)

    def list_all(self) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(f"{_SELECT} ORDER BY day_of_week, start_time, room_id;")).fetchall()
        return [_row(r) for r in rows]

    def replace_all(self, entries: List[Dict[str, Any]]) -> int:
        # One transaction: a failed row leaves the previous semester's timetable intact.
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM timetables;"))
            for e in entries:
                conn.execute(_INSERT, e)
        return len(entries)

    def add_entries(self, entries: List[Dict[str, Any]]) -> List[int]:
        with self.engine.begin() as conn:
            return [int(conn.execute(_INSERT, e).scalar()) for e in entries]

    def delete_entry(self, schedule_id: int) -> bool:
        with self.engine.begin() as conn:
            res = conn.execute(text("DELETE FROM timetables WHERE schedule_id = :id;"), {"id": schedule_id})
        return (res.rowcount or 0) > 0

    def source(self) -> str:
        # 'database' covers uploaded/edited sessions and init.sql's three demo rows alike; the
        # audit trail's timetable_update records say who changed the table and when.
        with self.engine.connect() as conn:
            return "seed" if self._table_empty(conn) else "database"
