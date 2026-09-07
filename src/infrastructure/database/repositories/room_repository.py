"""
CampusGrid AI: Room Repository Implementations
In-memory and PostgreSQL adapters for the campus room / zone inventory.

OWNER: Member 1 (Team Lead)
"""

from typing import List, Dict, Any, Optional
from sqlalchemy import text
from src.domain.interfaces.repositories import RoomRepository


class InMemoryRoomRepository(RoomRepository):
    """In-memory room inventory seeded with benchmark campus spaces."""

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
