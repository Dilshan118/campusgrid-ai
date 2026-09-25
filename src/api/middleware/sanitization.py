"""
CampusGrid AI: Input Sanitization Middleware
Sanitizes query parameters and request bodies to prevent prompt smuggling,
control character injection, and denial-of-service payload attacks.

Implemented as a pure ASGI middleware on purpose. Starlette's BaseHTTPMiddleware
replays the ORIGINAL request body to the endpoint no matter which Request object is
handed to call_next(), so a BaseHTTPMiddleware sanitizer silently sanitizes nothing.
Here the endpoint receives only the sanitized bytes.
"""

import json
import unicodedata
from typing import Any, List, Tuple
from urllib.parse import parse_qsl
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from src.domain.exceptions.base import DomainException

DEFAULT_MAX_BODY_BYTES = 1_048_576
MAX_STRING_LENGTH = 10_000


class MaliciousInputError(DomainException):
    def __init__(self, reason: str, status: int = 400):
        super().__init__(
            message=f"Request input rejected due to security policy: {reason}",
            error_code="MALICIOUS_INPUT_DETECTED",
            details={"reason": reason, "status": status}
        )


def sanitize_string(val: str, max_length: int = MAX_STRING_LENGTH) -> str:
    """Cleans control characters, null bytes, and normalizes Unicode."""
    if not isinstance(val, str):
        return val

    # 1. Reject or clean null bytes
    if "\x00" in val:
        val = val.replace("\x00", "")

    # 2. Length check to prevent buffer/memory exhaustion attacks
    if len(val) > max_length:
        val = val[:max_length]

    # 3. Unicode normalization (NFKC decomposes homoglyphs and compatibility chars)
    normalized = unicodedata.normalize("NFKC", val)

    # 4. Remove unprintable control characters except standard whitespace (\n, \r, \t)
    cleaned = "".join(
        ch for ch in normalized
        if unicodedata.category(ch)[0] != "C" or ch in "\n\r\t"
    )

    return cleaned


def sanitize_data_structure(data: Any) -> Any:
    """Recursively sanitizes dicts, lists, and strings."""
    if isinstance(data, dict):
        return {sanitize_string(k): sanitize_data_structure(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_data_structure(item) for item in data]
    elif isinstance(data, str):
        return sanitize_string(data)
    return data


def _has_control_characters(value: str) -> bool:
    return any(unicodedata.category(ch)[0] == "C" and ch not in "\n\r\t" for ch in value)


def _may_be_parsed_as_json(content_type: str) -> bool:
    """True for every body FastAPI may decode as JSON: application/json, any application/*+json,
    and (in older FastAPI releases) a body sent with no Content-Type at all. Checking only for
    'application/json' let 'application/vnd.api+json' carry unsanitized text to the agents."""
    media_type = content_type.split(";", 1)[0].strip()
    if not media_type:
        return True
    return media_type == "application/json" or (media_type.startswith("application/") and media_type.endswith("+json"))


def _reject(exc: MaliciousInputError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.details["status"],
        content={
            "success": False,
            "error_code": exc.error_code,
            "message": exc.message,
            "details": {"reason": exc.details["reason"]},
        },
    )


class InputSanitizationMiddleware:
    """ASGI middleware: body size limit, JSON body sanitization, query-string control-char rejection."""

    def __init__(self, app: ASGIApp, max_body_bytes: int = DEFAULT_MAX_BODY_BYTES):
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 1. Query parameters: they cannot be rewritten safely, so control characters are rejected.
        query_string = scope.get("query_string", b"").decode("latin-1")
        for key, value in parse_qsl(query_string, keep_blank_values=True):
            if _has_control_characters(key) or _has_control_characters(value):
                await _reject(MaliciousInputError(f"control characters in query parameter '{sanitize_string(key)}'"))(scope, receive, send)
                return

        headers: List[Tuple[bytes, bytes]] = list(scope.get("headers", []))
        header_map = {k.lower(): v for k, v in headers}

        declared_length = header_map.get(b"content-length")
        if declared_length is not None and declared_length.isdigit() and int(declared_length) > self.max_body_bytes:
            await _reject(MaliciousInputError("request body exceeds size limit", status=413))(scope, receive, send)
            return

        content_type = header_map.get(b"content-type", b"").decode("latin-1").lower()
        if not _may_be_parsed_as_json(content_type):
            await self.app(scope, receive, send)
            return

        # 2. Buffer the JSON body (bounded), sanitize it, and hand ONLY the sanitized bytes downstream.
        chunks: List[bytes] = []
        total = 0
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > self.max_body_bytes:
                await _reject(MaliciousInputError("request body exceeds size limit", status=413))(scope, receive, send)
                return
            chunks.append(chunk)
            more_body = message.get("more_body", False)

        body = b"".join(chunks)
        if body:
            try:
                parsed = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                parsed = None  # FastAPI's own validation returns the 422 for malformed JSON
            if parsed is not None:
                body = json.dumps(sanitize_data_structure(parsed)).encode("utf-8")

        if body:
            new_headers = [(k, v) for k, v in headers if k.lower() != b"content-length"]
            new_headers.append((b"content-length", str(len(body)).encode("latin-1")))
            scope = {**scope, "headers": new_headers}

        body_sent = False

        async def sanitized_receive() -> Message:
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, sanitized_receive, send)
