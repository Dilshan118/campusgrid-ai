"""
CampusGrid AI: Analytics Event Repository Implementations
In-memory and PostgreSQL adapters for web-analytics interaction events.

OWNER: Member 1 (Team Lead)
"""

import json
import threading
from typing import List, Optional
from sqlalchemy import text
from src.domain.interfaces.repositories import AnalyticsEventRepository
from src.domain.entities.analytics import AnalyticsEvent


class InMemoryAnalyticsEventRepository(AnalyticsEventRepository):
    """Process-local event store. Events are lost on restart; use postgres to persist them."""

    def __init__(self, max_events: int = 100_000):
        self._events: List[AnalyticsEvent] = []
        self._counter = 1
        self._max_events = max_events
        self._lock = threading.Lock()

    def record(self, event: AnalyticsEvent) -> int:
        with self._lock:
            event.event_id = self._counter
            self._counter += 1
            self._events.append(event.model_copy(deep=True))
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]
            return event.event_id

    def list_events(self, event_types: Optional[List[str]] = None, limit: int = 10_000) -> List[AnalyticsEvent]:
        selected = [e for e in self._events if not event_types or e.event_type in event_types]
        return [e.model_copy(deep=True) for e in selected[-limit:]]


class PostgresAnalyticsEventRepository(AnalyticsEventRepository):
    """PostgreSQL implementation (table: analytics_events in init.sql)."""

    def __init__(self, engine):
        self.engine = engine

    def record(self, event: AnalyticsEvent) -> int:
        with self.engine.begin() as conn:
            res = conn.execute(
                text("""
                    INSERT INTO analytics_events
                    (event_type, user_id, role, session_id, audit_log_id, ab_variant, intent,
                     query_text, rank, clause_reference, metadata, timestamp)
                    VALUES (:event_type, :user_id, :role, :session_id, :audit_log_id, :ab_variant, :intent,
                            :query_text, :rank, :clause_reference, :metadata, :ts)
                    RETURNING event_id;
                """),
                {
                    "event_type": event.event_type,
                    "user_id": event.user_id,
                    "role": event.role,
                    "session_id": event.session_id,
                    "audit_log_id": event.audit_log_id,
                    "ab_variant": event.ab_variant,
                    "intent": event.intent,
                    "query_text": event.query_text,
                    "rank": event.rank,
                    "clause_reference": event.clause_reference,
                    "metadata": json.dumps(event.metadata, default=str),
                    "ts": event.timestamp,
                }
            )
            event.event_id = int(res.scalar() or 0)
            return event.event_id

    def list_events(self, event_types: Optional[List[str]] = None, limit: int = 10_000) -> List[AnalyticsEvent]:
        where = "WHERE event_type = ANY(:types)" if event_types else ""
        params = {"lim": limit}
        if event_types:
            params["types"] = list(event_types)
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(f"""
                    SELECT event_id, event_type, user_id, role, session_id, audit_log_id, ab_variant,
                           intent, query_text, rank, clause_reference, metadata, timestamp
                    FROM (
                        SELECT * FROM analytics_events {where} ORDER BY event_id DESC LIMIT :lim
                    ) recent
                    ORDER BY event_id ASC;
                """),
                params
            ).fetchall()
        return [
            AnalyticsEvent(
                event_id=r[0], event_type=r[1], user_id=r[2], role=r[3], session_id=r[4],
                audit_log_id=r[5], ab_variant=r[6], intent=r[7], query_text=r[8], rank=r[9],
                clause_reference=r[10],
                metadata=r[11] if isinstance(r[11], dict) else json.loads(r[11] or "{}"),
                timestamp=r[12].isoformat() if hasattr(r[12], "isoformat") else str(r[12]),
            )
            for r in rows
        ]
