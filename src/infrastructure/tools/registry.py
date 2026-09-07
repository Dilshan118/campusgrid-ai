"""
CampusGrid AI: Tool Registry
Maintains registered tools for agent discovery and execution.
"""

from typing import Dict, List, Optional
from src.domain.interfaces.tool import Tool, ToolResult
from src.domain.exceptions.base import ToolExecutionError

class ToolRegistry:
    """Central registry of agent tools."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        return list(self._tools.values())

    def execute(self, tool_name: str, **kwargs) -> ToolResult:
        tool = self.get(tool_name)
        if not tool:
            raise ToolExecutionError(tool_name=tool_name, message=f"Tool '{tool_name}' not found in registry.")
        return tool.execute(**kwargs)
