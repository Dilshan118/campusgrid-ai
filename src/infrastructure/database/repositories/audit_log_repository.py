"""
CampusGrid AI: Audit Log Repository Implementations
In-memory and PostgreSQL adapters for the append-only audit trail.

OWNER: Member 1 (Team Lead)
"""

import json
from typing import List
from sqlalchemy import text
from src.domain.interfaces.repositories import AuditLogRepository
from src.domain.entities.audit import AuditRecord


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
                    SELECT log_id, timestamp, user_id, query_text, agent_sequence,
                           final_decision, human_approved, signature
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
