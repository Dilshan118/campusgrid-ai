"""
CampusGrid AI: Orchestrator Router
Runs the full multi-agent sequential pipeline: Query -> A1 -> A2 -> A3 -> A4 -> Approval Queue.
"""

from fastapi import APIRouter, Depends, HTTPException
from src.schemas.requests import OperatorQueryRequest
from src.schemas.responses import APIResponse
from src.application.container import Container
from src.api.dependencies.container import get_app_container

router = APIRouter(prefix="/api/orchestrator", tags=["Multi-Agent Orchestrator"])

@router.post("/query", response_model=APIResponse)
async def process_operator_query(
    request: OperatorQueryRequest,
    container: Container = Depends(get_app_container)
):
    res = container.orchestrator.execute({
        "query": request.query,
        "user_id": request.user_id,
        "session_id": request.session_id,
        "perturb_temp_delta_c": request.perturb_temp_delta_c,
        "perturb_occ_multiplier": request.perturb_occ_multiplier
    })

    if not res.success:
        raise HTTPException(status_code=500, detail=res.error)

    return APIResponse(
        success=True,
        data=res.data,
        execution_time_ms=res.execution_time_ms
    )
