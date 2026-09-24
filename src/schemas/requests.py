"""
CampusGrid AI: Public API Request Schemas
Pydantic DTOs for client request payloads.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

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

class WhatIfSimulationRequest(BaseModel):
    initial_temp_c: float = Field(default=24.0, ge=18.0, le=35.0)
    ambient_temp_delta_c: float = Field(default=0.0, ge=-10.0, le=15.0)
    occupancy_multiplier: float = Field(default=1.0, ge=0.0, le=5.0)
    date: Optional[str] = Field(default=None, pattern=ISO_DATE_PATTERN, description="Weather date; defaults to tomorrow")
    room: str = Field(default="LH-1", max_length=20, description="Room whose capacity bounds the simulated occupancy")

class OptimizationRunRequest(BaseModel):
    battery_capacity_kwh: float = Field(default=500.0, gt=0, le=10_000)
    max_charge_rate_kw: float = Field(default=100.0, gt=0, le=5_000)
    max_discharge_rate_kw: float = Field(default=100.0, gt=0, le=5_000)
    initial_soc_ratio: float = Field(default=0.50, ge=0.20, le=0.90)
    date: Optional[str] = Field(default=None, pattern=ISO_DATE_PATTERN, description="Forecast date; defaults to tomorrow")
    room: str = Field(default="LH-1", max_length=20)

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
    effective_date: Optional[str] = Field(
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

