"""
Unit tests for Member 3 (Agent 2: Digital Twin, 2R2C Thermal & Battery Physics).
Terminal Command to run:
    pytest tests/unit/test_member3_digital_twin.py -v
"""

import json
import pytest
from src.agents.digital_twin.thermal_model import BuildingThermalTwin
from src.agents.digital_twin.battery_dynamics import BatteryDynamicsModel
from src.agents.digital_twin.thermal_calibration import (
    fit_thermal_constants,
    generate_synthetic_reference_dataset,
)
from src.infrastructure.tools.simulation_tool import SimulationTool
from src.agents.digital_twin.agent import DigitalTwinAgent
from src.agents.digital_twin.mcp_server import MCPToolServer, create_digital_twin_mcp_server

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

def test_member3_fitted_constants_beat_guessed_constants():
    """Headline result: scipy.optimize.least_squares must recover physics constants
    that fit measured data far better than the guessed defaults (50.0, 2.5)."""
    ambient, occupants, hvac, measured = generate_synthetic_reference_dataset()
    report = fit_thermal_constants(
        initial_temp_c=24.0,
        ambient_temps=ambient,
        occupant_counts=occupants,
        hvac_power_kw=hvac,
        measured_indoor_temps_c=measured,
    )
    assert report.rmse_fitted < report.rmse_guessed
    assert report.accuracy_improvement_pct > 50.0

def test_member3_simulation_tool_delegates_to_thermal_model():
    """There must be exactly one implementation of the 2R2C equations: the tool's
    output has to match BuildingThermalTwin.simulate() bit-for-bit, not a second copy."""
    twin = BuildingThermalTwin(c_in=50.0, r_vent=2.5)
    expected = twin.simulate(
        initial_temp_c=24.0,
        ambient_temps=[30.0, 31.0, 29.0],
        occupant_counts=[50, 50, 50],
        hvac_power_kw=[10.0, 10.0, 10.0],
    )

    tool = SimulationTool(c_in=50.0, r_vent=2.5)
    result = tool.execute(
        initial_temp_c=24.0,
        ambient_temps=[30.0, 31.0, 29.0],
        occupant_counts=[50, 50, 50],
        hvac_power_kw=[10.0, 10.0, 10.0],
    )

    assert result.success is True
    assert result.data["indoor_temperatures_c"] == expected

@pytest.mark.parametrize(
    "kwargs",
    [
        {"initial_temp_c": -15.0, "ambient_temps": [24.0], "occupant_counts": [10], "hvac_power_kw": [5.0]},
        {"initial_temp_c": 24.0, "ambient_temps": [24.0], "occupant_counts": [10], "hvac_power_kw": [5000.0]},
        {"initial_temp_c": 24.0, "ambient_temps": [24.0], "occupant_counts": [-5], "hvac_power_kw": [5.0]},
        {"initial_temp_c": 24.0, "ambient_temps": [24.0, 24.0], "occupant_counts": [10], "hvac_power_kw": [5.0]},
    ],
)
def test_member3_simulation_tool_rejects_impossible_parameters(kwargs):
    """The tool boundary must refuse impossible commands (e.g. -15C, 5000kW) instead
    of silently running them through the physics — this is the MCP security mitigation."""
    tool = SimulationTool()
    result = tool.execute(**kwargs)
    assert result.success is False
    assert result.error is not None

def test_member3_what_if_scenarios():
    """The three required what-if perturbations must actually change the inputs they
    claim to, and each must report a comfort verdict plus a deviation figure."""
    agent = DigitalTwinAgent()
    ambient = [25.0] * 10
    occupancy = [50] * 10
    hvac = [8.0] * 10

    results = agent.run_what_if_scenarios(
        initial_temp_c=24.0,
        ambient_temperatures_c=ambient,
        occupancy_counts=occupancy,
        hvac_power_kw=hvac,
    )

    assert set(results.keys()) == {"heatwave", "crowd_surge", "solar_dropout"}
    assert results["heatwave"]["ambient_temperatures_c"] == [29.0] * 10
    assert results["crowd_surge"]["occupancy_counts"] == [100] * 10
    assert results["solar_dropout"]["hvac_power_kw"] == [4.0] * 10

    baseline = agent.execute({
        "initial_temp_c": 24.0,
        "ambient_temperatures_c": ambient,
        "occupancy_counts": occupancy,
        "hvac_power_kw": hvac,
    }).data

    # Less cooling headroom (hotter outside, or less HVAC power) must not leave the
    # building any cooler than the unperturbed baseline plan.
    assert results["heatwave"]["simulated_indoor_temps_c"][-1] >= baseline["simulated_indoor_temps_c"][-1]
    assert results["solar_dropout"]["simulated_indoor_temps_c"][-1] >= baseline["simulated_indoor_temps_c"][-1]

    for scenario_result in results.values():
        assert "is_thermal_feasible" in scenario_result
        assert "max_temp_deviation_c" in scenario_result

def test_member3_agent_wires_battery_trajectory_into_output():
    """The guide's §6 contract requires the agent hand Developer 3 a 48-value battery
    charge trajectory + violation count. This must be real BatteryDynamicsModel output,
    not omitted or faked, and must match what the model produces standalone."""
    agent = DigitalTwinAgent()
    ambient = [25.0] * 6
    occupancy = [50] * 6
    hvac = [8.0] * 6
    charge = [50.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    discharge = [0.0, 0.0, 0.0, 60.0, 60.0, 0.0]
    initial_soc = 250.0

    result = agent.execute({
        "initial_temp_c": 24.0,
        "ambient_temperatures_c": ambient,
        "occupancy_counts": occupancy,
        "hvac_power_kw": hvac,
        "battery_initial_soc_kwh": initial_soc,
        "battery_charge_kw": charge,
        "battery_discharge_kw": discharge,
    }).data

    assert "battery_soc_trajectory_kwh" in result
    assert "battery_soc_violations_count" in result
    assert "is_battery_feasible" in result
    assert len(result["battery_soc_trajectory_kwh"]) == 6

    expected_trajectory, expected_violations = BatteryDynamicsModel().simulate_soc_trajectory(
        initial_soc_kwh=initial_soc,
        charge_kw_series=charge,
        discharge_kw_series=discharge,
    )
    assert result["battery_soc_trajectory_kwh"] == expected_trajectory
    assert result["battery_soc_violations_count"] == expected_violations

def test_member3_agent_defaults_to_idle_battery_when_no_plan_given():
    """Callers that only care about thermal feasibility (the existing what-if API
    route) supply no battery plan at all — this must not break, and must report a
    flat, violation-free trajectory rather than silently omitting battery data."""
    agent = DigitalTwinAgent()
    result = agent.execute({
        "initial_temp_c": 24.0,
        "ambient_temperatures_c": [28.0] * 4,
        "occupancy_counts": [50] * 4,
    }).data

    assert len(result["battery_soc_trajectory_kwh"]) == 4
    assert result["battery_soc_violations_count"] == 0
    assert result["is_battery_feasible"] is True

def test_member3_mcp_tools_list_exposes_simulation_tool():
    server = create_digital_twin_mcp_server()
    response = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    assert response["id"] == 1
    tools = response["result"]["tools"]
    assert any(t["name"] == "simulate_building_thermal_dynamics" for t in tools)
    assert "inputSchema" in tools[0]

def test_member3_mcp_tools_call_executes_real_simulation():
    server = create_digital_twin_mcp_server()
    response = server.handle_request({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "simulate_building_thermal_dynamics",
            "arguments": {
                "initial_temp_c": 24.0,
                "ambient_temps": [24.0, 24.0],
                "occupant_counts": [0, 0],
                "hvac_power_kw": [0.0, 0.0],
            },
        },
    })

    assert response["result"]["isError"] is False
    payload = json.loads(response["result"]["content"][0]["text"])
    assert len(payload["indoor_temperatures_c"]) == 2

@pytest.mark.parametrize(
    "arguments",
    [
        {"initial_temp_c": -15.0, "ambient_temps": [24.0], "occupant_counts": [10], "hvac_power_kw": [5.0]},
        {"initial_temp_c": 24.0, "ambient_temps": [24.0], "occupant_counts": [10], "hvac_power_kw": [5000.0]},
    ],
)
def test_member3_mcp_tools_call_rejects_spoofed_parameters(arguments):
    """MCP parameter spoofing: a client commanding -15C or 5000kW over the wire must
    be rejected at the tool boundary, not accepted as a valid protocol call."""
    server = create_digital_twin_mcp_server()
    response = server.handle_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "simulate_building_thermal_dynamics", "arguments": arguments},
    })
    assert response["result"]["isError"] is True

def test_member3_mcp_unknown_method_returns_json_rpc_error():
    server = MCPToolServer()
    response = server.handle_request({"jsonrpc": "2.0", "id": 4, "method": "tools/delete"})
    assert response["error"]["code"] == -32601

def test_member3_mcp_malformed_envelope_rejected():
    server = MCPToolServer()
    response = server.handle_request({"id": 5, "method": "tools/list"})  # missing "jsonrpc"
    assert response["error"]["code"] == -32600

def test_member3_mcp_unknown_tool_name_rejected():
    server = MCPToolServer()
    response = server.handle_request({
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {"name": "delete_all_battery_data", "arguments": {}},
    })
    assert response["error"]["code"] == -32602
