"""
CampusGrid AI: Model Context Protocol (MCP) Router
Serves the registered agent tools (digital-twin simulation, campus weather) to MCP clients as
JSON-RPC 2.0 over HTTP: one JSON-RPC message per POST, answered with the JSON-RPC response.

Authenticated and role-checked like every other planning route, and the request body passes the
same sanitization middleware. Tool arguments are validated at the tool boundary (SimulationTool).
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse, Response
from src.application.container import Container
from src.api.dependencies.container import get_app_container
from src.api.middleware.auth import require_roles, ROLES_PLANNERS

router = APIRouter(prefix="/api/mcp", tags=["Model Context Protocol"])


@router.post("")
def mcp_json_rpc(
    message: Any = Body(..., description="One JSON-RPC 2.0 message (initialize, ping, tools/list, tools/call)"),
    _user=Depends(require_roles(ROLES_PLANNERS)),
    container: Container = Depends(get_app_container),
):
    reply: Optional[Dict[str, Any]] = container.mcp_server.handle_request(message)
    if reply is None:  # a notification: accepted, nothing to answer
        return Response(status_code=202)
    return JSONResponse(content=reply)
