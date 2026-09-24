"""
CampusGrid AI: Agent 2 — MCP Tool Server for the Digital Twin Simulator
Module Owner: Member 3 (Digital Twin, Cyber-Physical Physics & Simulation)

Exposes `SimulationTool` over the Model Context Protocol's JSON-RPC 2.0 wire format
(https://modelcontextprotocol.io) instead of a plain Python function call. This is what
makes the assignment brief's "defined agent communication protocols (e.g. MCP, HTTP,
sockets)" requirement honest for Agent 2 — HTTP is already covered by the REST
endpoints; this is the MCP leg, and it is also Student 4's own audit target: you cannot
credibly test MCP parameter spoofing or tool interception against a plain function call.

Implements the two methods an MCP client actually calls on a tool server:
  - "tools/list": tool discovery, returning name/description/inputSchema
  - "tools/call": tool invocation, returning MCP's CallToolResult content/isError shape

`handle_request()` is deliberately transport-agnostic: it takes and returns plain
JSON-RPC dicts, so it can be driven directly (as the tests do) or wired to a stdio/SSE
transport via the official `mcp` SDK. Adding that SDK as a dependency needs a line in
`pyproject.toml`, which is team-lead-owned (see TEAM_GUIDES/OWNERSHIP.md) — filed as a
`WIRE: mcp SDK transport` request rather than edited here. The protocol-level logic
below (method dispatch, tool discovery, argument validation, error shapes) is identical
regardless of which transport eventually carries these JSON-RPC messages.
"""

import json
from typing import Any, Dict, List, Optional

from src.domain.interfaces.tool import Tool
from src.infrastructure.tools.simulation_tool import SimulationTool

MCP_PROTOCOL_VERSION = "2024-11-05"

# JSON-RPC 2.0 reserved error codes (https://www.jsonrpc.org/specification#error_object)
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602


class MCPToolServer:
    """A minimal, spec-faithful MCP server exposing one or more `Tool` instances."""

    def __init__(self, tools: Optional[List[Tool]] = None):
        registered = tools if tools is not None else [SimulationTool()]
        self._tools: Dict[str, Tool] = {tool.name: tool for tool in registered}

    def _tool_definitions(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.parameters_schema,
            }
            for tool in self._tools.values()
        ]

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches one JSON-RPC 2.0 request to the matching MCP method.

        Malformed envelopes, unknown methods, unknown tools, and invalid tool
        arguments are all rejected with a JSON-RPC error object rather than raising —
        an MCP server must never crash on an adversarial or malformed message, since
        that message may come from an untrusted client.
        """
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or "method" not in request:
            return self._error(request.get("id") if isinstance(request, dict) else None,
                                INVALID_REQUEST, "Invalid Request: not a JSON-RPC 2.0 envelope")

        request_id = request.get("id")
        method = request["method"]
        params = request.get("params", {}) or {}

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "serverInfo": {"name": "campusgrid-digital-twin", "version": "1.0.0"},
                    "capabilities": {"tools": {}},
                },
            }

        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": self._tool_definitions()}}

        if method == "tools/call":
            return self._handle_tools_call(request_id, params)

        return self._error(request_id, METHOD_NOT_FOUND, f"Method not found: {method!r}")

    def _handle_tools_call(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(params, dict):
            return self._error(request_id, INVALID_PARAMS, "Invalid params: expected an object")

        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not isinstance(arguments, dict):
            return self._error(request_id, INVALID_PARAMS, "Invalid params: 'arguments' must be an object")

        tool = self._tools.get(tool_name)
        if tool is None:
            return self._error(request_id, INVALID_PARAMS, f"Unknown tool: {tool_name!r}")

        try:
            result = tool.execute(**arguments)
        except (TypeError, ValueError) as exc:
            return self._error(request_id, INVALID_PARAMS, f"Invalid arguments for {tool_name!r}: {exc}")

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(result.data, default=str)}],
                "isError": not result.success,
                **({"error": result.error} if result.error else {}),
            },
        }


def create_digital_twin_mcp_server() -> MCPToolServer:
    """Wiring entry point: the MCP server this deliverable exposes to the pipeline."""
    return MCPToolServer(tools=[SimulationTool()])
