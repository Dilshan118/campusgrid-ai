"""
Unit tests for Member 3 (Agent 2: Digital Twin, 2R2C Thermal & Battery Physics).
Terminal Command to run:
    pytest tests/unit/test_member3_digital_twin.py -v
"""

import pytest
from src.agents.digital_twin.thermal_model import BuildingThermalTwin
from src.agents.digital_twin.battery_dynamics import BatteryDynamicsModel

def test_member3_thermal_model_simulation():
    twin = BuildingThermalTwin(c_in=50.0, r_vent=2.5)

    try:
        temps = twin.simulate(
            initial_temp_c=24.0,
            ambient_temps=[24.0, 24.0, 24.0],
            occupant_counts=[0, 0, 0],
            hvac_power_kw=[0.0, 0.0, 0.0]
        )
    except NotImplementedError:
        pytest.skip("Member 3 has not implemented BuildingThermalTwin.simulate() yet.")

    assert len(temps) == 3
    assert all(abs(t - 24.0) < 0.05 for t in temps)

def test_member3_thermal_occupant_heat_gain():
    twin = BuildingThermalTwin(c_in=50.0, r_vent=2.5)

    try:
        temps = twin.simulate(
            initial_temp_c=24.0,
            ambient_temps=[24.0, 24.0],
            occupant_counts=[100, 100],
            hvac_power_kw=[0.0, 0.0]
        )
    except NotImplementedError:
        pytest.skip("Member 3 has not implemented BuildingThermalTwin.simulate() yet.")

    # 100 occupants produce 10 kW of heat; temp must rise
    assert temps[-1] > 24.0

def test_member3_battery_soc_tracking():
    bess = BatteryDynamicsModel(capacity_kwh=500.0, min_soc_pct=0.20, max_soc_pct=0.90)

    try:
        soc_history, violations = bess.simulate_soc_trajectory(
            initial_soc_kwh=250.0,
            charge_kw_series=[50.0, 50.0],
            discharge_kw_series=[0.0, 0.0]
        )
    except NotImplementedError:
        pytest.skip("Member 3 has not implemented BatteryDynamicsModel.simulate_soc_trajectory() yet.")

    assert len(soc_history) == 2
    assert soc_history[-1] > 250.0
    assert violations == 0
