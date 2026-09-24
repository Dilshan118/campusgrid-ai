"""
CampusGrid AI: Abstract Repository Interfaces
Contract for database persistence operations across campus entities.
Decouples domain services and agents from SQLAlchemy/Postgres.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from src.domain.entities.telemetry import TelemetryInterval
from src.domain.entities.audit import AuditRecord
from src.domain.entities.analytics import AnalyticsEvent

class RoomRepository(ABC):
    """Abstract repository for campus physical rooms and zones."""

    @abstractmethod
    def get_by_id(self, room_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def list_all(self) -> List[Dict[str, Any]]:
        pass

class TimetableRepository(ABC):
    """Abstract repository for lecture timetables and expected occupancy."""

    @abstractmethod
    def get_schedule_for_day(self, day_of_week: int) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_room_occupancy(self, room_id: str, time_slot: str, day_of_week: int) -> int:
        pass

class MeterHistoryRepository(ABC):
    """Abstract repository for historical sub-meter telemetry records."""

    @abstractmethod
    def get_historical_profile(self, date_str: str) -> List[TelemetryInterval]:
        """Returns 48 half-hour telemetry intervals for a specified benchmark date."""
        pass

    @abstractmethod
    def append_reading(self, reading: TelemetryInterval) -> bool:
        pass

class AuditLogRepository(ABC):
    """Abstract repository for append-only audit trail.

    Implementations must sign every appended row with compute_audit_signature(), chaining it
    to the previous row's signature, and must never update or delete an existing row.
    """

    @abstractmethod
    def log_transaction(self, record: AuditRecord) -> int:
        """Appends an immutable, hash-chained audit record and returns its ID."""
        pass

    @abstractmethod
    def list_recent(self, limit: int = 50) -> List[AuditRecord]:
        """Newest first."""
        pass

    @abstractmethod
    def get_by_id(self, log_id: int) -> Optional[AuditRecord]:
        pass

    @abstractmethod
    def get_decision_for(self, log_id: int) -> Optional[AuditRecord]:
        """Returns the approval_decision row whose parent_log_id is log_id, if one exists."""
        pass

    @abstractmethod
    def list_all_ascending(self) -> List[AuditRecord]:
        """Every row, oldest first, for hash-chain verification."""
        pass

class AnalyticsEventRepository(ABC):
    """Abstract repository for web-analytics interaction events (append-only)."""

    @abstractmethod
    def record(self, event: AnalyticsEvent) -> int:
        pass

    @abstractmethod
    def list_events(self, event_types: Optional[List[str]] = None, limit: int = 10_000) -> List[AnalyticsEvent]:
        """Oldest first, optionally filtered to the given event types."""
        pass
