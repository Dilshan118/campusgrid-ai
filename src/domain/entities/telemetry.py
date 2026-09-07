"""
CampusGrid AI: Telemetry Domain Entities
Pure domain representations of microgrid sensor readings, power flows, and forecasts.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

class TelemetryInterval(BaseModel):
    """Represents a single 30-minute interval of campus microgrid telemetry."""
    time_slot: str = Field(..., description="Timestamp in HH:MM format (e.g., '14:00')")
    base_load_kw: float = Field(..., ge=0.0, description="Baseline campus power consumption in kW")
    solar_gen_kw: float = Field(..., ge=0.0, description="Rooftop solar PV generation in kW")
    outdoor_temp_c: float = Field(..., description="Ambient outdoor temperature in Celsius")
    grid_tariff_lkr_kwh: float = Field(..., gt=0.0, description="PUCSL grid electricity tariff in LKR/kWh")
    zone_occupancy_count: int = Field(default=0, ge=0, description="Estimated total occupant count")

class PowerForecast(BaseModel):
    """24-hour day-ahead demand and generation forecast with confidence intervals."""
    time_slots: List[str]
    forecast_demand_kw: List[float]
    forecast_solar_kw: List[float]
    lower_bound_kw: List[float]
    upper_bound_kw: List[float]
    anomaly_indices: List[int] = Field(default_factory=list)
    model_version: str = "v1.0-lightgbm"

class WeatherObservation(BaseModel):
    """Ambient weather condition observation."""
    time_slot: str
    temperature_c: float
    humidity_pct: Optional[float] = None
    solar_irradiance_wm2: Optional[float] = None
    condition_summary: Optional[str] = None
