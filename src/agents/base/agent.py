"""
CampusGrid AI: Base Agent Abstract Class
Enforces standard lifecycle hooks, timing, error wrapping, and observability tracing.
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from src.agents.base.state import AgentExecutionResult
from src.infrastructure.observability.tracer import Tracer
from src.domain.exceptions.base import DomainException, ProviderException

logger = logging.getLogger("campusgrid.agents")


def _client_safe_error(exc: Exception) -> str:
    """The error text an agent result may carry. It travels to API clients, so raw exception
    and provider text (hosts, SQL, credentials, file paths) is logged server-side, never returned."""
    if isinstance(exc, ProviderException):
        provider = exc.details.get("provider", "external")
        return f"[{exc.error_code}] The {provider} provider call failed; details are in the server log."
    if isinstance(exc, DomainException):
        return f"[{exc.error_code}] {exc.message}"
    return f"Unexpected agent error ({type(exc).__name__}); details are in the server log."


class BaseAgent(ABC):
    """Abstract base class for all specialized domain agents."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def initialize(self) -> None:
        """Lifecycle hook called before executing tasks."""
        pass

    def cleanup(self) -> None:
        """Lifecycle hook called after execution or on failure."""
        pass

    @abstractmethod
    def _run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Internal execution logic to be implemented by child agents."""
        pass

    def execute(self, input_data: Dict[str, Any]) -> AgentExecutionResult:
        """Standardized execution wrapper with timing, tracing, and error isolation."""
        start_time = time.time()
        self.initialize()

        try:
            output_data = self._run(input_data)
            duration_ms = (time.time() - start_time) * 1000.0

            Tracer.log_agent_execution(
                agent_name=self.name,
                input_summary={k: str(v)[:100] for k, v in input_data.items()},
                output_summary={k: str(v)[:100] for k, v in output_data.items()},
                duration_ms=duration_ms
            )

            citations = output_data.get("citations", [])

            return AgentExecutionResult(
                agent_name=self.name,
                success=True,
                data=output_data,
                execution_time_ms=duration_ms,
                citations=citations
            )
        except DomainException as de:
            duration_ms = (time.time() - start_time) * 1000.0
            if isinstance(de, ProviderException):
                logger.warning("%s: provider failure: %s (request_id=%s)", self.name, de.message, Tracer.get_request_id())
            return AgentExecutionResult(
                agent_name=self.name,
                success=False,
                data={},
                error=_client_safe_error(de),
                execution_time_ms=duration_ms
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000.0
            logger.exception("%s: unexpected error (request_id=%s)", self.name, Tracer.get_request_id())
            return AgentExecutionResult(
                agent_name=self.name,
                success=False,
                data={},
                error=_client_safe_error(e),
                execution_time_ms=duration_ms
            )
        finally:
            self.cleanup()
