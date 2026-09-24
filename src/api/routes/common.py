"""
CampusGrid AI: Shared Route Helpers
"""

from datetime import date, timedelta
from typing import Optional
from src.agents.base.state import AgentExecutionResult
from src.domain.exceptions.base import AgentExecutionError
from src.schemas.responses import APIResponse


def agent_response(result: AgentExecutionResult) -> APIResponse:
    """Wraps a successful agent result; a failed one becomes an HTTP 502 with the standard error body."""
    if not result.success:
        raise AgentExecutionError(result.agent_name, result.error)
    return APIResponse(success=True, data=result.data, execution_time_ms=result.execution_time_ms)


def default_planning_date(requested: Optional[str] = None) -> str:
    """Day-ahead planning: tomorrow unless a date was supplied."""
    return requested or (date.today() + timedelta(days=1)).isoformat()
