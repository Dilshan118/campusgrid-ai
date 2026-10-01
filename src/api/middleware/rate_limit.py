"""
CampusGrid AI: Per-User Rate Limiting for Expensive Endpoints (SEC-08)
A planning request can make up to three language-model calls, two MILP solves and several
embedding lookups, so an authenticated account looping on it can exhaust the LLM quota or the
solver threads. Each user gets a sliding one-minute budget across all such endpoints.

In-process, like the login throttle: correct for the single-instance deployment; a multi-instance
deployment needs a shared store (e.g. Redis) behind the same interface.
"""

import threading
import time
from typing import Any, Dict, List
from fastapi import Depends
from src.application.container import Container
from src.api.dependencies.container import get_app_container
from src.api.middleware.auth import get_current_user
from src.domain.exceptions.base import DomainException

WINDOW_SECONDS = 60.0


class RateLimitExceededError(DomainException):
    def __init__(self, retry_after_seconds: int, limit: int):
        super().__init__(
            message=f"Too many planning requests: at most {limit} per minute. Try again shortly.",
            error_code="RATE_LIMIT_EXCEEDED",
            details={"status": 429, "retry_after_seconds": retry_after_seconds},
        )


class SlidingWindowLimiter:
    """Allows `limit` hits per key in any WINDOW_SECONDS window."""

    def __init__(self):
        self._hits: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int) -> None:
        if limit <= 0:
            return
        now = time.monotonic()
        with self._lock:
            window = [t for t in self._hits.get(key, []) if now - t < WINDOW_SECONDS]
            if len(window) >= limit:
                self._hits[key] = window
                raise RateLimitExceededError(int(WINDOW_SECONDS - (now - window[0])) + 1, limit)
            window.append(now)
            self._hits[key] = window


planner_limiter = SlidingWindowLimiter()


async def limit_planner_requests(
    user: Dict[str, Any] = Depends(get_current_user),
    container: Container = Depends(get_app_container),
) -> None:
    """Route dependency: counts the request against the caller's per-minute planning budget."""
    planner_limiter.hit(user["user_id"], container.settings.planner_rate_limit_per_minute)
