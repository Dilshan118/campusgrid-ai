"""
CampusGrid AI: Public API Request Schemas
Pydantic DTOs for client request payloads.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

class OperatorQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Natural-language operator query")
    user_id: str = Field(default="facility_director", description="Authenticated user identifier")
    session_id: Optional[str] = None
    perturb_temp_delta_c: float = Field(default=0.0, description="What-if ambient temperature delta")
    perturb_occ_multiplier: float = Field(default=1.0, ge=0.0, le=5.0, description="What-if occupancy multiplier")

class WhatIfSimulationRequest(BaseModel):
    initial_temp_c: float = Field(default=24.0, ge=18.0, le=35.0)
    ambient_temp_delta_c: float = Field(default=0.0, ge=-10.0, le=15.0)
    occupancy_multiplier: float = Field(default=1.0, ge=0.0, le=5.0)

class OptimizationRunRequest(BaseModel):
    battery_capacity_kwh: float = Field(default=500.0, gt=0)
    max_charge_rate_kw: float = Field(default=100.0, gt=0)
    max_discharge_rate_kw: float = Field(default=100.0, gt=0)
    initial_soc_ratio: float = Field(default=0.50, ge=0.20, le=0.90)

class RAGSearchRequest(BaseModel):
    query: str = Field(..., min_length=2)
    top_k: int = Field(default=2, ge=1, le=5)

class AuditApprovalRequest(BaseModel):
    log_id: int
    approved: bool
    operator_notes: Optional[str] = None
