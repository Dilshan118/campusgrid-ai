"""
CampusGrid AI: Public API Request Schemas
Pydantic DTOs for client request payloads.
"""

from datetime import date
from typing import Annotated, List, Optional
from pydantic import AfterValidator, BaseModel, Field, field_validator
from src.shared.datetime_utils import campus_today

class OperatorQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000, description="Natural-language operator query")
    user_id: Optional[str] = Field(
        default=None,
        description="Ignored. The acting user always comes from the bearer token; kept for backward compatibility."
    )
    session_id: Optional[str] = Field(default=None, max_length=100)
    perturb_temp_delta_c: Optional[float] = Field(
        default=None, ge=-10.0, le=15.0,
        description="What-if ambient temperature delta. Omit to use the value stated in the query text."
    )
    perturb_occ_multiplier: Optional[float] = Field(
        default=None, ge=0.0, le=5.0,
        description="What-if occupancy multiplier. Omit to use the value stated in the query text."
    )

ISO_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


def validate_iso_date(value: Optional[str]) -> Optional[str]:
    """The pattern checks the shape; this rejects impossible dates such as 2026-13-45."""
    if value is None:
        return value
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError("must be a real calendar date in YYYY-MM-DD format")
    return value


IsoDate = Annotated[str, AfterValidator(validate_iso_date)]

class WhatIfSimulationRequest(BaseModel):
    initial_temp_c: float = Field(default=24.0, ge=18.0, le=35.0)
    ambient_temp_delta_c: float = Field(default=0.0, ge=-10.0, le=15.0)
    occupancy_multiplier: float = Field(default=1.0, ge=0.0, le=5.0)
    date: Optional[IsoDate] = Field(default=None, pattern=ISO_DATE_PATTERN, description="Weather date; defaults to tomorrow")
    room: str = Field(default="LH-1", max_length=20, description="Listed room to simulate (ignored when room_type is given)")
    room_type: Optional[str] = Field(
        default=None, max_length=40,
        description="Custom (unlisted) room: its venue type, e.g. 'lecture_hall', 'study_area' — see "
                     "GET /api/simulation/venues. When given, `room` is ignored."
    )
    seating_capacity: Optional[int] = Field(default=None, ge=1, le=2000, description="Custom room only")
    num_acs: Optional[int] = Field(default=None, ge=1, le=50, description="Custom room only")
    precool_minutes: int = Field(
        default=0, ge=0, le=180, multiple_of=30,
        description="Start the ACs this long before the room opens (0, 30, 60 ... 180)."
    )

    @field_validator("date")
    @classmethod
    def not_in_the_past(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and date.fromisoformat(value) < campus_today():
            raise ValueError("must be today or a later date — a what-if simulation looks ahead, not back")
        return value

class OptimizationRunRequest(BaseModel):
    battery_capacity_kwh: float = Field(default=500.0, gt=0, le=10_000)
    max_charge_rate_kw: float = Field(default=100.0, gt=0, le=5_000)
    max_discharge_rate_kw: float = Field(default=100.0, gt=0, le=5_000)
    initial_soc_ratio: float = Field(default=0.50, ge=0.20, le=0.90)
    date: Optional[IsoDate] = Field(default=None, pattern=ISO_DATE_PATTERN, description="Forecast date; defaults to tomorrow")
    room: str = Field(default="LH-1", max_length=20)
    # Flexible loads and billing state (all optional; omitted = site settings).
    hvac_flex_percent: Optional[float] = Field(
        default=None, ge=0, le=50,
        description="How far air-conditioning load may move per half-hour, energy-neutral (0 = HVAC not flexed)",
    )
    shiftable_load_kw: float = Field(default=0.0, ge=0, le=2000, description="Rated power of shiftable Tier-2 equipment (pumps, EV chargers)")
    shiftable_hours: float = Field(default=0.0, ge=0, le=24, multiple_of=0.5, description="Hours per day that equipment must run")
    shiftable_usual_start: str = Field(default="08:00", pattern=r"^([01]\d|2[0-3]):(00|30)$", description="When it normally starts")
    month_to_date_peak_kva: Optional[float] = Field(default=None, ge=0, le=100_000, description="Highest demand this billing month so far (CEB bill / meter)")
    power_factor: Optional[float] = Field(default=None, gt=0.5, le=1.0)

class RAGSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000)
    top_k: int = Field(default=2, ge=1, le=5)
    session_id: Optional[str] = Field(default=None, max_length=100)

class AuditApprovalRequest(BaseModel):
    log_id: int = Field(..., ge=1)
    approved: bool
    operator_notes: Optional[str] = Field(default=None, max_length=2000)
    acknowledge_warnings: bool = Field(
        default=False,
        description="Must be true to approve a recommendation that carries safety or verification warnings."
    )

class RAGIngestRequest(BaseModel):
    text: Optional[str] = Field(default=None, max_length=200_000, description="Raw markdown or text clause to ingest")
    source_document: Optional[str] = Field(default="Custom Regulatory Document", max_length=255, description="Title of the source regulation")
    effective_date: Optional[IsoDate] = Field(
        default="2024-01-01", pattern=ISO_DATE_PATTERN, description="Effective date (YYYY-MM-DD)"
    )

class AnalyticsEventRequest(BaseModel):
    """A dashboard interaction. The user, role and A/B variant are set by the server, never by the client."""
    event_type: str = Field(..., max_length=40)
    audit_log_id: Optional[int] = Field(default=None, ge=1)
    session_id: Optional[str] = Field(default=None, max_length=100)
    query_text: Optional[str] = Field(default=None, max_length=500)
    rank: Optional[int] = Field(default=None, ge=1, le=100)
    clause_reference: Optional[str] = Field(default=None, max_length=200)


class TimetableUploadRequest(BaseModel):
    """A whole timetable as CSV. Sent as lines, not one string: the sanitization middleware caps any
    single string at 10,000 characters, which would silently cut a long file."""
    csv_lines: List[str] = Field(..., min_length=2, max_length=5001, description="CSV text split into lines, header first")
    mode: str = Field(default="replace", pattern=r"^(replace|append)$",
                      description="'replace' swaps in a new semester's timetable; 'append' adds sessions")
    dry_run: bool = Field(default=True, description="Validate and preview only; nothing is written")
    filename: Optional[str] = Field(default=None, max_length=200)

class TimetableSessionRequest(BaseModel):
    room_id: str = Field(..., min_length=1, max_length=20)
    course_code: str = Field(..., min_length=1, max_length=50)
    day: str = Field(..., min_length=1, max_length=10, description="Mon..Sun, Monday..Sunday or 1..7")
    start_time: str = Field(..., max_length=5, description="HH:MM, 24-hour")
    end_time: str = Field(..., max_length=5, description="HH:MM, 24-hour")
    expected_students: int = Field(..., ge=0, le=5000)

class ExecutionReportRequest(BaseModel):
    log_id: int = Field(..., ge=1, description="The approved dispatch plan")
    outcome: str = Field(..., pattern=r"^(completed|partial|not_executed)$")
    executed_on: Optional[IsoDate] = Field(default=None, pattern=ISO_DATE_PATTERN)
    notes: Optional[str] = Field(default=None, max_length=2000)
    deviations: Optional[str] = Field(default=None, max_length=2000,
                                      description="What was done differently from the plan (times, kW, rooms)")

class RegulationSubmissionRequest(BaseModel):
    """A regulation document for quarantine and second-person review. Sent as lines: the sanitization
    middleware caps any single string at 10,000 characters."""
    text_lines: List[str] = Field(..., min_length=1, max_length=20_000)
    title: str = Field(..., min_length=3, max_length=255, description="Document title; a new version needs its own title (e.g. with its year)")
    publisher: str = Field(..., min_length=2, max_length=20, description="Code from GET /api/rag/sources, e.g. PUCSL")
    reference: str = Field(..., min_length=2, max_length=200, description="Gazette / decision / circular number")
    effective_date: IsoDate = Field(..., pattern=ISO_DATE_PATTERN)
    source_url: Optional[str] = Field(default=None, max_length=500)
    supersedes: Optional[str] = Field(default=None, max_length=255, description="Title of the document this one replaces")
    filename: Optional[str] = Field(default=None, max_length=200)

    @field_validator("text_lines")
    @classmethod
    def bounded_text(cls, lines: List[str]) -> List[str]:
        if sum(len(line) + 1 for line in lines) > 200_000:
            raise ValueError("the document is longer than 200,000 characters")
        if not "".join(lines).strip():
            raise ValueError("the document is empty")
        return lines

class RegulationReviewRequest(BaseModel):
    approved: bool
    notes: Optional[str] = Field(default=None, max_length=2000)
