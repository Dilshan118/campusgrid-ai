"""
CampusGrid AI: Repository Adapters

Split one file per domain entity so that ownership is unambiguous and two developers
never edit the same module:

    room_repository.py           -> Member 1 (Team Lead)
    audit_log_repository.py      -> Member 1 (Team Lead)
    analytics_event_repository.py -> Member 1 (Team Lead)
    timetable_repository.py      -> Member 2 (Developer 1)
    meter_history_repository.py  -> Member 2 (Developer 1)

This __init__ is the shared re-export surface and is owned by the Team Lead.
"""

from src.infrastructure.database.repositories.room_repository import (
    InMemoryRoomRepository,
    PostgresRoomRepository,
)
from src.infrastructure.database.repositories.audit_log_repository import (
    InMemoryAuditLogRepository,
    PostgresAuditLogRepository,
)
from src.infrastructure.database.repositories.analytics_event_repository import (
    InMemoryAnalyticsEventRepository,
    PostgresAnalyticsEventRepository,
)
from src.infrastructure.database.repositories.timetable_repository import (
    InMemoryTimetableRepository,
    PostgresTimetableRepository,
)
from src.infrastructure.database.repositories.meter_history_repository import (
    InMemoryMeterHistoryRepository,
    PostgresMeterHistoryRepository,
)

__all__ = [
    "InMemoryRoomRepository",
    "PostgresRoomRepository",
    "InMemoryAuditLogRepository",
    "PostgresAuditLogRepository",
    "InMemoryAnalyticsEventRepository",
    "PostgresAnalyticsEventRepository",
    "InMemoryTimetableRepository",
    "PostgresTimetableRepository",
    "InMemoryMeterHistoryRepository",
    "PostgresMeterHistoryRepository",
]
