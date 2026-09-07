"""
CampusGrid AI: In-Memory Seeded Repositories
Zero-dependency repository implementations initialized with benchmark campus data.
Enables instant local execution and hermetic unit testing.
"""

import os
import csv
from typing import List, Dict, Any, Optional
from src.domain.interfaces.repositories import (
    RoomRepository,
    TimetableRepository,
    MeterHistoryRepository,
    AuditLogRepository,
)
from src.domain.entities.telemetry import TelemetryInterval
from src.domain.entities.audit import AuditRecord

class InMemoryRoomRepository(RoomRepository):
    """In-memory room inventory."""

    def __init__(self):
        self._rooms: Dict[str, Dict[str, Any]] = {
            "LH-1": {
                "room_id": "LH-1",
                "building_name": "Main Academic Complex",
                "room_type": "Lecture Hall",
                "max_capacity": 250,
                "chiller_zone_id": "ZONE-A1"
            },
            "AUD-1": {
                "room_id": "AUD-1",
                "building_name": "Auditorium Wing",
                "room_type": "Auditorium",
                "max_capacity": 600,
                "chiller_zone_id": "ZONE-B1"
            },
            "LAB-3": {
                "room_id": "LAB-3",
                "building_name": "Computing Building",
                "room_type": "Computer Lab",
                "max_capacity": 80,
                "chiller_zone_id": "ZONE-C2"
            }
        }

    def get_by_id(self, room_id: str) -> Optional[Dict[str, Any]]:
        return self._rooms.get(room_id)

    def list_all(self) -> List[Dict[str, Any]]:
        return list(self._rooms.values())

class InMemoryTimetableRepository(TimetableRepository):
    """In-memory academic timetable."""

    def __init__(self):
        self._schedules = [
            {"schedule_id": 1, "room_id": "LH-1", "course_code": "IT3041", "day_of_week": 1, "start_time": "08:30", "end_time": "11:30", "expected_students": 220},
            {"schedule_id": 2, "room_id": "LH-1", "course_code": "IT3020", "day_of_week": 1, "start_time": "13:00", "end_time": "16:00", "expected_students": 240},
            {"schedule_id": 3, "room_id": "AUD-1", "course_code": "EN1010", "day_of_week": 1, "start_time": "09:00", "end_time": "12:00", "expected_students": 550},
        ]

    def get_schedule_for_day(self, day_of_week: int) -> List[Dict[str, Any]]:
        return [s for s in self._schedules if s["day_of_week"] == day_of_week]

    def get_room_occupancy(self, room_id: str, time_slot: str, day_of_week: int) -> int:
        for s in self._schedules:
            if s["room_id"] == room_id and s["day_of_week"] == day_of_week:
                if s["start_time"] <= time_slot <= s["end_time"]:
                    return s["expected_students"]
        return 0

class InMemoryMeterHistoryRepository(MeterHistoryRepository):
    """In-memory historical meter logs loaded from sample_campus_seed.csv."""

    def __init__(self, seed_csv_path: Optional[str] = None):
        self._records: List[TelemetryInterval] = []
        self._load_seed_data(seed_csv_path)

    def _load_seed_data(self, seed_csv_path: Optional[str]):
        # Potential seed paths
        paths = [
            seed_csv_path,
            "backend/data/seeds/sample_campus_seed.csv",
            "../backend/data/seeds/sample_campus_seed.csv",
            os.path.join(os.path.dirname(__file__), "../../../backend/data/seeds/sample_campus_seed.csv")
        ]

        loaded = False
        for p in paths:
            if p and os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            self._records.append(TelemetryInterval(
                                time_slot=row["time_slot"],
                                base_load_kw=float(row["base_load_kw"]),
                                solar_gen_kw=float(row["solar_gen_kw"]),
                                outdoor_temp_c=float(row["outdoor_temp_c"]),
                                grid_tariff_lkr_kwh=float(row["grid_tariff_lkr_kwh"]),
                                zone_occupancy_count=int(row["zone_occupancy_count"])
                            ))
                    loaded = True
                    break
                except Exception:
                    continue

        if not loaded or len(self._records) == 0:
            # Synthetic 48 interval fallback if seed CSV not found
            for h in range(24):
                for m in (0, 30):
                    slot = f"{h:02d}:{m:02d}"
                    base = 200.0 + (300.0 if 8 <= h <= 17 else 0.0)
                    solar = 150.0 if 9 <= h <= 15 else 0.0
                    temp = 26.0 + (5.0 if 10 <= h <= 15 else 0.0)
                    tariff = 58.0 if 18 <= h < 23 else (15.0 if h < 6 else 30.0)
                    self._records.append(TelemetryInterval(
                        time_slot=slot,
                        base_load_kw=base,
                        solar_gen_kw=solar,
                        outdoor_temp_c=temp,
                        grid_tariff_lkr_kwh=tariff,
                        zone_occupancy_count=100 if 8 <= h <= 16 else 10
                    ))

    def get_historical_profile(self, date_str: str) -> List[TelemetryInterval]:
        return list(self._records)

    def append_reading(self, reading: TelemetryInterval) -> bool:
        self._records.append(reading)
        return True

class InMemoryAuditLogRepository(AuditLogRepository):
    """In-memory append-only audit trail."""

    def __init__(self):
        self._logs: List[AuditRecord] = []
        self._counter = 1

    def log_transaction(self, record: AuditRecord) -> int:
        record.log_id = self._counter
        self._counter += 1
        self._logs.append(record)
        return record.log_id

    def list_recent(self, limit: int = 50) -> List[AuditRecord]:
        return list(reversed(self._logs[-limit:]))
