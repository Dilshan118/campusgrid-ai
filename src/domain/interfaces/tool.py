"""
CampusGrid AI: Abstract Tool Interface
Standard contract for executable tools and Model Context Protocol (MCP) adapters.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class ToolResult(BaseModel):
    success: bool
    data: Any
    error: Optional[str] = None
    execution_time_ms: float = 0.0

class Tool(ABC):
    """Abstract interface for agent-executable tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    @abstractmethod
    def parameters_schema(self) -> Dict[str, Any]:
        """JSON Schema defining the expected parameters."""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        pass
