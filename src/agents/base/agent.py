"""
CampusGrid AI: Base Agent Abstract Class
Enforces standard lifecycle hooks, timing, error wrapping, and observability tracing.
"""

import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from src.agents.base.state import AgentExecutionResult
from src.infrastructure.observability.tracer import Tracer
from src.domain.exceptions.base import DomainException

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
            return AgentExecutionResult(
                agent_name=self.name,
                success=False,
                data={},
                error=f"[{de.error_code}] {de.message}",
                execution_time_ms=duration_ms
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000.0
            return AgentExecutionResult(
                agent_name=self.name,
                success=False,
                data={},
                error=f"Unexpected agent error: {str(e)}",
                execution_time_ms=duration_ms
            )
        finally:
            self.cleanup()
