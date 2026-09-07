"""
CampusGrid AI: Observability & Execution Tracer
Structured logging, correlation IDs (request_id, trace_id), latency measurement, and token tracking.
"""

import time
import uuid
import logging
from typing import Dict, Any, Optional
from contextvars import ContextVar

# Context variables for request tracing across async / sync boundaries
_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
_trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="")

logger = logging.getLogger("campusgrid.tracer")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '{"time": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

class Tracer:
    """Provides structured execution tracing and metrics collection."""

    @staticmethod
    def set_trace_context(request_id: Optional[str] = None, trace_id: Optional[str] = None):
        req_id = request_id or str(uuid.uuid4())
        trc_id = trace_id or str(uuid.uuid4())
        _request_id_ctx.set(req_id)
        _trace_id_ctx.set(trc_id)
        return req_id, trc_id

    @staticmethod
    def get_request_id() -> str:
        req = _request_id_ctx.get()
        return req if req else str(uuid.uuid4())

    @staticmethod
    def get_trace_id() -> str:
        trc = _trace_id_ctx.get()
        return trc if trc else str(uuid.uuid4())

    @staticmethod
    def log_agent_execution(
        agent_name: str,
        input_summary: Dict[str, Any],
        output_summary: Dict[str, Any],
        duration_ms: float
    ):
        logger.info(
            f"Agent Execution: {agent_name} | Latency: {duration_ms:.2f}ms | "
            f"RequestID: {Tracer.get_request_id()} | Input: {input_summary} | Output: {output_summary}"
        )

    @staticmethod
    def log_llm_call(
        model: str,
        prompt_tokens: Optional[int],
        completion_tokens: Optional[int],
        duration_ms: float
    ):
        logger.info(
            f"LLM Call: {model} | Latency: {duration_ms:.2f}ms | "
            f"Tokens: Prompt={prompt_tokens}, Completion={completion_tokens} | RequestID: {Tracer.get_request_id()}"
        )
