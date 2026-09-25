"""
CampusGrid AI: Shared Route Helpers
"""

from datetime import date, timedelta
from typing import Optional
from src.agents.base.state import AgentExecutionResult
from src.domain.exceptions.base import AgentExecutionError, DomainException
from src.schemas.requests import validate_iso_date
from src.schemas.responses import APIResponse


def agent_response(result: AgentExecutionResult) -> APIResponse:
    """Wraps a successful agent result; a failed one becomes an HTTP 502 with the standard error body."""
    if not result.success:
        raise AgentExecutionError(result.agent_name, result.error)
    return APIResponse(success=True, data=result.data, execution_time_ms=result.execution_time_ms)


def checked_date(value: Optional[str], field: str = "date") -> Optional[str]:
    """Validates a date taken from a query parameter (request bodies use the IsoDate schema type)."""
    try:
        return validate_iso_date(value)
    except ValueError as exc:
        raise DomainException(
            message=f"'{field}' {exc}.", error_code="VALIDATION_ERROR", details={"status": 422, "field": field}
        )


def default_planning_date(requested: Optional[str] = None) -> str:
    """Day-ahead planning: tomorrow unless a date was supplied."""
    return checked_date(requested) or (date.today() + timedelta(days=1)).isoformat()


def default_history_date(requested: Optional[str] = None) -> str:
    """Historical telemetry: the most recent full day (yesterday) unless a date was supplied."""
    return checked_date(requested) or (date.today() - timedelta(days=1)).isoformat()
