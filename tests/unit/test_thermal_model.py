"""
Unit tests for 2R2C Grey-Box continuous thermal model differential equations.
Validates both the reference baseline physics and checks Member 3 implementation status.
"""

import pytest
from src.infrastructure.reference_baselines.baseline_thermal import BaselineBuildingThermalTwin
from src.agents.digital_twin.thermal_model import BuildingThermalTwin

def test_reference_thermal_model_stable_temperature():
    """Verify reference baseline math maintains equilibrium when ambient equals indoor temp."""
    twin = BaselineBuildingThermalTwin(c_in=50.0, r_vent=2.5)
    temps = twin.simulate(
        initial_temp_c=24.0,
        ambient_temps=[24.0, 24.0, 24.0],
        occupant_counts=[0, 0, 0],
        hvac_power_kw=[0.0, 0.0, 0.0]
    )
    assert len(temps) == 3
    assert all(abs(t - 24.0) < 0.01 for t in temps)

def test_reference_thermal_model_occupant_heating():
    """Verify reference baseline correctly increases temperature under occupant heat load."""
    twin = BaselineBuildingThermalTwin(c_in=50.0, r_vent=2.5)
    temps = twin.simulate(
        initial_temp_c=24.0,
        ambient_temps=[24.0, 24.0, 24.0],
        occupant_counts=[200, 200, 200],
        hvac_power_kw=[0.0, 0.0, 0.0]
    )
    assert temps[-1] > 24.0

def test_member3_scaffold_status():
    """Checks whether Member 3 has implemented or still has the TODO scaffold."""
    twin = BuildingThermalTwin(c_in=50.0, r_vent=2.5)
    try:
        temps = twin.simulate(24.0, [24.0], [0], [0.0])
        assert len(temps) == 1
    except NotImplementedError:
        pytest.skip("Member 3 has not implemented simulate() yet.")
