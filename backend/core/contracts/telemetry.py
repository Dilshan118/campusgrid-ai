"""
CampusGrid AI: Telemetry Contract Models
Defines immutable Pydantic schemas for live sensor readings and campus power flows.
"""

from pydantic import BaseModel, Field

class TelemetryInterval(BaseModel):
    """Represents a single 30-minute interval of campus microgrid telemetry."""
    time_slot: str = Field(..., description="Timestamp in HH:MM format (e.g., '14:00')")
    base_load_kw: float = Field(..., ge=0.0, description="Baseline campus power consumption in kW")
    solar_gen_kw: float = Field(..., ge=0.0, description="Rooftop solar PV generation in kW")
    outdoor_temp_c: float = Field(..., description="Ambient outdoor temperature in Celsius")
    grid_tariff_lkr_kwh: float = Field(..., gt=0.0, description="PUCSL grid electricity tariff in LKR/kWh")
    zone_occupancy_count: int = Field(default=0, ge=0, description="Estimated total occupant count")
