"""
CampusGrid AI: PostgreSQL Database Repositories
Concrete repository implementations communicating with Neon Serverless PostgreSQL.
"""

import json
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from src.domain.interfaces.repositories import (
    RoomRepository,
    TimetableRepository,
    MeterHistoryRepository,
    AuditLogRepository,
)
from src.domain.entities.telemetry import TelemetryInterval
from src.domain.entities.audit import AuditRecord

class PostgresRoomRepository(RoomRepository):
    """PostgreSQL implementation of RoomRepository."""

    def __init__(self, engine):
        self.engine = engine

    def get_by_id(self, room_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT room_id, building_name, room_type, max_capacity, chiller_zone_id FROM rooms WHERE room_id = :id;"),
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
                text("SELECT room_id, building_name, room_type, max_capacity, chiller_zone_id FROM rooms;")
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

class PostgresAuditLogRepository(AuditLogRepository):
    """PostgreSQL implementation of AuditLogRepository."""

    def __init__(self, engine):
        self.engine = engine

    def log_transaction(self, record: AuditRecord) -> int:
        with self.engine.begin() as conn:
            res = conn.execute(
                text("""
                    INSERT INTO audit_log_store
                    (user_id, query_text, agent_sequence, final_decision, human_approved, signature)
                    VALUES (:user_id, :query, :seq, :decision, :approved, :sig)
                    RETURNING log_id;
                """),
                {
                    "user_id": record.user_id,
                    "query": record.query_text,
                    "seq": json.dumps(record.agent_sequence),
                    "decision": json.dumps(record.final_decision),
                    "approved": record.human_approved,
                    "sig": record.signature
                }
            )
            return int(res.scalar() or 0)

    def list_recent(self, limit: int = 50) -> List[AuditRecord]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT log_id, timestamp, user_id, query_text, agent_sequence, final_decision, human_approved, signature
                    FROM audit_log_store
                    ORDER BY log_id DESC
                    LIMIT :lim;
                """),
                {"lim": limit}
            ).fetchall()

            records = []
            for r in rows:
                seq = r[4] if isinstance(r[4], dict) else json.loads(r[4] or "{}")
                dec = r[5] if isinstance(r[5], dict) else json.loads(r[5] or "{}")
                records.append(AuditRecord(
                    log_id=r[0],
                    timestamp=str(r[1]),
                    user_id=r[2],
                    query_text=r[3],
                    agent_sequence=seq,
                    final_decision=dec,
                    human_approved=bool(r[6]),
                    signature=r[7]
                ))
            return records
