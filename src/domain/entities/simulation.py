"""
CampusGrid AI: Simulation Domain Entities
Represents continuous building thermal states, battery electrochemical dynamics, and perturbations.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

class ThermalState(BaseModel):
    """Instantaneous thermal state of a campus building zone."""
    indoor_temp_c: float
    wall_temp_c: float
    ambient_temp_c: float
    occupant_count: int = 0
    hvac_power_kw: float = 0.0

class ThermalSimulationResult(BaseModel):
    """Output of 2R2C building thermal physics simulation across horizon."""
    time_slots: List[str]
    indoor_temperatures_c: List[float]
    ambient_temperatures_c: List[float]
    hvac_power_kw: List[float]
    comfort_min_limit_c: float = 21.0
    comfort_max_limit_c: float = 25.5
    comfort_violation_count: int = 0
    max_temp_deviation_c: float = 0.0
    is_feasible: bool = True

class BatteryState(BaseModel):
    """Battery Energy Storage System (BESS) state."""
    capacity_kwh: float = 500.0
    current_soc_pct: float = Field(..., ge=0.0, le=1.0)
    current_soc_kwh: float
    min_soc_pct: float = 0.20
    max_soc_pct: float = 0.90
    max_power_kw: float = 100.0

class PerturbationScenario(BaseModel):
    """What-if scenario parameters for digital twin simulation."""
    scenario_name: str
    ambient_temp_delta_c: float = 0.0
    occupancy_multiplier: float = 1.0
    solar_scaling_factor: float = 1.0
    chiller_precool_hours: int = 0
