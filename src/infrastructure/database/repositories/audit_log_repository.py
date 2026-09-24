"""
CampusGrid AI: Audit Log Repository Implementations
In-memory and PostgreSQL adapters for the append-only, hash-chained audit trail.

OWNER: Member 1 (Team Lead)
"""

import json
import threading
from typing import Dict, List, Optional
from sqlalchemy import text
from src.domain.interfaces.repositories import AuditLogRepository
from src.domain.entities.audit import (
    AuditRecord,
    RECORD_APPROVAL_DECISION,
    compute_audit_signature,
)


class InMemoryAuditLogRepository(AuditLogRepository):
    """In-memory append-only audit trail."""

    def __init__(self):
        self._logs: List[AuditRecord] = []
        self._counter = 1
        self._lock = threading.Lock()

    def log_transaction(self, record: AuditRecord) -> int:
        with self._lock:
            previous = self._logs[-1].signature if self._logs else None
            record.previous_signature = previous
            record.signature = compute_audit_signature(record, previous)
            record.log_id = self._counter
            self._counter += 1
            # Store a copy so later mutation of the caller's object cannot rewrite history.
            self._logs.append(record.model_copy(deep=True))
            return record.log_id

    def list_recent(self, limit: int = 50, record_type: Optional[str] = None) -> List[AuditRecord]:
        with self._lock:
            logs = [r for r in self._logs if record_type is None or r.record_type == record_type]
        return [r.model_copy(deep=True) for r in reversed(logs[-limit:])]

    def get_decisions_for(self, log_ids: List[int]) -> Dict[int, AuditRecord]:
        wanted = set(log_ids)
        with self._lock:
            return {
                r.parent_log_id: r.model_copy(deep=True) for r in self._logs
                if r.record_type == RECORD_APPROVAL_DECISION and r.parent_log_id in wanted
            }

    def get_by_id(self, log_id: int) -> Optional[AuditRecord]:
        for r in self._logs:
            if r.log_id == log_id:
                return r.model_copy(deep=True)
        return None

    def get_decision_for(self, log_id: int) -> Optional[AuditRecord]:
        for r in self._logs:
            if r.record_type == RECORD_APPROVAL_DECISION and r.parent_log_id == log_id:
                return r.model_copy(deep=True)
        return None

    def list_all_ascending(self) -> List[AuditRecord]:
        return [r.model_copy(deep=True) for r in self._logs]


_SELECT_COLUMNS = (
    "log_id, timestamp, user_id, query_text, agent_sequence, final_decision, human_approved, "
    "record_type, approval_status, parent_log_id, previous_signature, signature"
)


def _row_to_record(r) -> AuditRecord:
    seq = r[4] if isinstance(r[4], dict) else json.loads(r[4] or "{}")
    dec = r[5] if isinstance(r[5], dict) else json.loads(r[5] or "{}")
    return AuditRecord(
        log_id=r[0],
        timestamp=r[1].isoformat() if hasattr(r[1], "isoformat") else str(r[1]),
        user_id=r[2],
        query_text=r[3],
        agent_sequence=seq,
        final_decision=dec,
        human_approved=bool(r[6]),
        record_type=r[7],
        approval_status=r[8],
        parent_log_id=r[9],
        previous_signature=r[10],
        signature=r[11],
    )


class PostgresAuditLogRepository(AuditLogRepository):
    """PostgreSQL implementation of AuditLogRepository (table: audit_log_store in init.sql)."""

    def __init__(self, engine):
        self.engine = engine

    def log_transaction(self, record: AuditRecord) -> int:
        with self.engine.begin() as conn:
            # Serialize writers so two concurrent inserts cannot both chain to the same predecessor.
            conn.execute(text("LOCK TABLE audit_log_store IN SHARE ROW EXCLUSIVE MODE;"))
            previous = conn.execute(
                text("SELECT signature FROM audit_log_store ORDER BY log_id DESC LIMIT 1;")
            ).scalar()
            record.previous_signature = previous
            record.signature = compute_audit_signature(record, previous)
            res = conn.execute(
                text("""
                    INSERT INTO audit_log_store
                    (timestamp, user_id, query_text, agent_sequence, final_decision, human_approved,
                     record_type, approval_status, parent_log_id, previous_signature, signature)
                    VALUES (:ts, :user_id, :query, :seq, :decision, :approved,
                            :record_type, :approval_status, :parent_log_id, :prev_sig, :sig)
                    RETURNING log_id;
                """),
                {
                    "ts": record.timestamp,
                    "user_id": record.user_id,
                    "query": record.query_text,
                    "seq": json.dumps(record.agent_sequence, default=str),
                    "decision": json.dumps(record.final_decision, default=str),
                    "approved": record.human_approved,
                    "record_type": record.record_type,
                    "approval_status": record.approval_status,
                    "parent_log_id": record.parent_log_id,
                    "prev_sig": previous,
                    "sig": record.signature,
                }
            )
            record.log_id = int(res.scalar() or 0)
            return record.log_id

    def list_recent(self, limit: int = 50, record_type: Optional[str] = None) -> List[AuditRecord]:
        where = "WHERE record_type = :rt" if record_type else ""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(f"SELECT {_SELECT_COLUMNS} FROM audit_log_store {where} ORDER BY log_id DESC LIMIT :lim;"),
                {"lim": limit, "rt": record_type}
            ).fetchall()
        return [_row_to_record(r) for r in rows]

    def get_decisions_for(self, log_ids: List[int]) -> Dict[int, AuditRecord]:
        if not log_ids:
            return {}
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT {_SELECT_COLUMNS} FROM audit_log_store "
                    "WHERE record_type = :rt AND parent_log_id = ANY(:ids);"
                ),
                {"rt": RECORD_APPROVAL_DECISION, "ids": list(log_ids)}
            ).fetchall()
        return {r[9]: _row_to_record(r) for r in rows}

    def get_by_id(self, log_id: int) -> Optional[AuditRecord]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT {_SELECT_COLUMNS} FROM audit_log_store WHERE log_id = :id;"),
                {"id": log_id}
            ).fetchone()
        return _row_to_record(row) if row else None

    def get_decision_for(self, log_id: int) -> Optional[AuditRecord]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    f"SELECT {_SELECT_COLUMNS} FROM audit_log_store "
                    "WHERE parent_log_id = :id AND record_type = :rt ORDER BY log_id LIMIT 1;"
                ),
                {"id": log_id, "rt": RECORD_APPROVAL_DECISION}
            ).fetchone()
        return _row_to_record(row) if row else None

    def list_all_ascending(self) -> List[AuditRecord]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(f"SELECT {_SELECT_COLUMNS} FROM audit_log_store ORDER BY log_id ASC;")
            ).fetchall()
        return [_row_to_record(r) for r in rows]
