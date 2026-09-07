"""
CampusGrid AI: Request Tracing Middleware
Injects correlation IDs (X-Request-ID, X-Trace-ID) and measures overall HTTP transaction latency.
"""

import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from src.infrastructure.observability.tracer import Tracer

class RequestTracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        trc_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())

        Tracer.set_trace_context(request_id=req_id, trace_id=trc_id)
        start_time = time.time()

        response: Response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000.0

        response.headers["X-Request-ID"] = req_id
        response.headers["X-Trace-ID"] = trc_id
        response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"

        return response
