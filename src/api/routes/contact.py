"""Public contact endpoints."""

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import APIRouter, Request

from src.application.services.pilot_email_service import (
    PilotEmailDeliveryError,
    PilotEmailNotConfigured,
    send_pilot_inquiry,
)
from src.domain.exceptions.base import DomainException
from src.schemas.requests import PilotInquiryRequest
from src.schemas.responses import APIResponse

router = APIRouter(prefix="/api/contact", tags=["Contact"])


class PilotSubmissionLimiter:
    """Small per-process limit for the anonymous contact form."""

    def __init__(self, limit: int = 5, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, client_key: str) -> None:
        now = time.monotonic()
        with self._lock:
            events = self._events[client_key]
            while events and now - events[0] >= self.window_seconds:
                events.popleft()
            if len(events) >= self.limit:
                retry = max(1, int(self.window_seconds - (now - events[0])) + 1)
                raise DomainException(
                    message="Too many pilot inquiries. Please try again shortly.",
                    error_code="RATE_LIMIT_EXCEEDED",
                    details={"status": 429, "retry_after_seconds": retry},
                )
            events.append(now)


submission_limiter = PilotSubmissionLimiter()


@router.post("/pilot", response_model=APIResponse)
def submit_pilot_inquiry(payload: PilotInquiryRequest, request: Request):
    client_key = request.client.host if request.client else "unknown"
    submission_limiter.check(client_key)

    # Quietly accept but discard likely bots. This avoids exposing honeypot behavior.
    if payload.website:
        return APIResponse(success=True, data={"accepted": True})

    inquiry = payload.model_dump(exclude={"website"})
    try:
        send_pilot_inquiry(inquiry)
    except PilotEmailNotConfigured as exc:
        raise DomainException(
            message="Pilot inquiry email is not configured. Please contact the site administrator.",
            error_code="CONTACT_DELIVERY_UNAVAILABLE",
            details={"status": 503},
        ) from exc
    except PilotEmailDeliveryError as exc:
        raise DomainException(
            message="We could not deliver your inquiry. Please try again later.",
            error_code="CONTACT_DELIVERY_FAILED",
            details={"status": 503},
        ) from exc

    return APIResponse(success=True, data={"accepted": True})
