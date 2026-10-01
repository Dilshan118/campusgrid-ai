"""
CampusGrid AI: Room Repository Implementations
In-memory and PostgreSQL adapters for the campus room / zone inventory.

OWNER: Member 1 (Team Lead)
"""

from typing import List, Dict, Any, Optional
from sqlalchemy import text
from src.domain.interfaces.repositories import RoomRepository


# Seed inventory — keep identical to the rooms INSERT in backend/data/init.sql.
# room_type must match a venue type in src/agents/digital_twin/room_presets.py. Room IDs pair a
# unique number with each type so the NLP parser's "<type> <number>" aliases never collide.
SEED_ROOMS: List[Dict[str, Any]] = [
    {"room_id": "LH-1", "building_name": "Main Academic Complex", "room_type": "Lecture Hall", "max_capacity": 250, "chiller_zone_id": "ZONE-A1"},
    {"room_id": "LH-2", "building_name": "Main Academic Complex", "room_type": "Lecture Hall", "max_capacity": 150, "chiller_zone_id": "ZONE-A1"},
    {"room_id": "LH-3", "building_name": "Main Academic Complex", "room_type": "Lecture Hall", "max_capacity": 100, "chiller_zone_id": "ZONE-A2"},
    {"room_id": "LH-4", "building_name": "New Academic Building", "room_type": "Lecture Hall", "max_capacity": 200, "chiller_zone_id": "ZONE-D1"},
    {"room_id": "LH-5", "building_name": "New Academic Building", "room_type": "Lecture Hall", "max_capacity": 60, "chiller_zone_id": "ZONE-D1"},
    {"room_id": "LAB-1", "building_name": "Computing Building", "room_type": "Computer Lab", "max_capacity": 40, "chiller_zone_id": "ZONE-C1"},
    {"room_id": "LAB-2", "building_name": "Computing Building", "room_type": "Computer Lab", "max_capacity": 60, "chiller_zone_id": "ZONE-C1"},
    {"room_id": "LAB-3", "building_name": "Computing Building", "room_type": "Computer Lab", "max_capacity": 80, "chiller_zone_id": "ZONE-C2"},
    {"room_id": "SLAB-1", "building_name": "Science Block", "room_type": "Science Lab", "max_capacity": 25, "chiller_zone_id": "ZONE-S1"},
    {"room_id": "SLAB-2", "building_name": "Science Block", "room_type": "Science Lab", "max_capacity": 35, "chiller_zone_id": "ZONE-S1"},
    {"room_id": "SLAB-3", "building_name": "Engineering Building", "room_type": "Science Lab", "max_capacity": 30, "chiller_zone_id": "ZONE-E1"},
    {"room_id": "AUD-1", "building_name": "Auditorium Wing", "room_type": "Auditorium", "max_capacity": 600, "chiller_zone_id": "ZONE-B1"},
    {"room_id": "AUD-2", "building_name": "Business School", "room_type": "Auditorium", "max_capacity": 300, "chiller_zone_id": "ZONE-B2"},
    {"room_id": "STDY-1", "building_name": "Library", "room_type": "Study Area", "max_capacity": 150, "chiller_zone_id": "ZONE-L1"},
    {"room_id": "STDY-2", "building_name": "Library", "room_type": "Study Area", "max_capacity": 60, "chiller_zone_id": "ZONE-L1"},
    {"room_id": "STDY-3", "building_name": "Student Centre", "room_type": "Study Area", "max_capacity": 80, "chiller_zone_id": "ZONE-T1"},
    {"room_id": "DRW-1", "building_name": "Architecture Building", "room_type": "Drawing Room", "max_capacity": 40, "chiller_zone_id": "ZONE-R1"},
    {"room_id": "DRW-2", "building_name": "Engineering Building", "room_type": "Drawing Room", "max_capacity": 60, "chiller_zone_id": "ZONE-E2"},
    {"room_id": "SEM-1", "building_name": "Main Academic Complex", "room_type": "Seminar Room", "max_capacity": 30, "chiller_zone_id": "ZONE-A2"},
    {"room_id": "SEM-2", "building_name": "Business School", "room_type": "Seminar Room", "max_capacity": 20, "chiller_zone_id": "ZONE-B2"},
]


class InMemoryRoomRepository(RoomRepository):
    """In-memory room inventory seeded with benchmark campus spaces."""

    def __init__(self):
        self._rooms: Dict[str, Dict[str, Any]] = {r["room_id"]: dict(r) for r in SEED_ROOMS}

    def get_by_id(self, room_id: str) -> Optional[Dict[str, Any]]:
        return self._rooms.get(room_id)

    def list_all(self) -> List[Dict[str, Any]]:
        return list(self._rooms.values())


class PostgresRoomRepository(RoomRepository):
    """PostgreSQL implementation of RoomRepository."""

    def __init__(self, engine):
        self.engine = engine

    def get_by_id(self, room_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT room_id, building_name, room_type, max_capacity, chiller_zone_id "
                    "FROM rooms WHERE room_id = :id;"
                ),
                {"id": room_id}
            ).fetchone()
            if row:
                return {
                    "room_id": row[0],
                    "building_name": row[1],
                    "room_type": row[2],
                    "max_capacity": row[3],
                    "chiller_zone_id": row[4]
                }
        return None

    def list_all(self) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT room_id, building_name, room_type, max_capacity, chiller_zone_id "
                    "FROM rooms;"
                )
            ).fetchall()
            return [
                {
                    "room_id": r[0],
                    "building_name": r[1],
                    "room_type": r[2],
                    "max_capacity": r[3],
                    "chiller_zone_id": r[4]
                }
                for r in rows
            ]
