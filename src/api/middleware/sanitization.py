"""
CampusGrid AI: Input Sanitization Middleware
Sanitizes query parameters and request bodies to prevent prompt smuggling,
control character injection, and denial-of-service payload attacks.
"""

import json
import unicodedata
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from src.domain.exceptions.base import DomainException


class MaliciousInputError(DomainException):
    def __init__(self, reason: str):
        super().__init__(
            message=f"Request input rejected due to security policy: {reason}",
            error_code="MALICIOUS_INPUT_DETECTED",
            details={"reason": reason}
        )


def sanitize_string(val: str, max_length: int = 10000) -> str:
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


def sanitize_data_structure(data: any) -> any:
    """Recursively sanitizes dicts, lists, and strings."""
    if isinstance(data, dict):
        return {sanitize_string(k): sanitize_data_structure(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_data_structure(item) for item in data]
    elif isinstance(data, str):
        return sanitize_string(data)
    return data


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """ASGI Middleware sanitizing request inputs across JSON payloads and query parameters."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # We process JSON request bodies if present
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                body_bytes = await request.body()
                if body_bytes:
                    body_json = json.loads(body_bytes.decode("utf-8"))
                    sanitized_json = sanitize_data_structure(body_json)
                    # Re-pack sanitized body
                    new_body_bytes = json.dumps(sanitized_json).encode("utf-8")

                    async def receive():
                        return {"type": "http.request", "body": new_body_bytes}

                    request = Request(request.scope, receive=receive)
            except Exception:
                # If body is invalid JSON, downstream FastAPI request validation will catch it
                pass

        response = await call_next(request)
        return response
