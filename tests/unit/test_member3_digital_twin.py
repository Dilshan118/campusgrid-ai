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
    calibration_solar_gain_kw,
)
from src.infrastructure.tools.simulation_tool import SimulationTool
from src.agents.digital_twin.agent import DigitalTwinAgent
from src.agents.digital_twin.mcp_server import MCPToolServer, create_digital_twin_mcp_server
from src.agents.digital_twin.room_presets import (
    ROOM_TYPE_PRESETS,
    build_venue_catalogue,
    list_room_type_presets,
    preset_key_for,
    resolve_room_config,
    suggest_ac_count,
)
from src.agents.digital_twin.operating_hours import occupied_mask, operating_hours_for
from src.infrastructure.database.repositories.room_repository import SEED_ROOMS
from src.shared.datetime_utils import campus_today
from datetime import date, timedelta

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
        solar_gain_kw=calibration_solar_gain_kw(len(ambient)),
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
    # A solar dropout halves the sunshine, not the air-conditioning.
    assert results["solar_dropout"]["hvac_power_kw"] == hvac
    assert results["solar_dropout"]["perturbation_applied"]["solar_scaling_factor"] == 0.5

    baseline = agent.execute({
        "initial_temp_c": 24.0,
        "ambient_temperatures_c": ambient,
        "occupancy_counts": occupancy,
        "hvac_power_kw": hvac,
    }).data

    # Hotter outside must not leave the building any cooler than the unperturbed plan.
    assert results["heatwave"]["simulated_indoor_temps_c"][-1] >= baseline["simulated_indoor_temps_c"][-1]

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

# -----------------------------------------------------------------------------
# Room-type presets (hypothetical room configuration for the what-if simulator)
# -----------------------------------------------------------------------------

def test_member3_lecture_hall_preset_matches_calibration():
    """The Lecture Hall preset is the one grounded in calibration output, not an estimate.
    Re-runs the calibration so the hard-coded constants cannot drift from what it fits,
    and checks the fit recovers the synthetic room it was generated from."""
    from src.agents.digital_twin.thermal_calibration import (
        CALIBRATION_SEATS, TRUE_C_IN, TRUE_R_VENT, run_calibration_report,
    )
    report = run_calibration_report()
    config = resolve_room_config("lecture_hall", capacity=CALIBRATION_SEATS)
    assert abs(config.c_in - report.fitted_c_in) / report.fitted_c_in < 0.01
    assert abs(config.r_vent - report.fitted_r_vent) / report.fitted_r_vent < 0.01
    assert abs(report.fitted_c_in - TRUE_C_IN) / TRUE_C_IN < 0.05
    assert abs(report.fitted_r_vent - TRUE_R_VENT) / TRUE_R_VENT < 0.05

def test_member3_resolve_room_config_scales_with_capacity():
    small = resolve_room_config("lecture_hall", capacity=50)
    large = resolve_room_config("lecture_hall", capacity=250)
    assert large.c_in > small.c_in, "A bigger room must carry more thermal mass"

def test_member3_resolve_room_config_defaults_ac_count_by_type():
    lecture_hall = resolve_room_config("lecture_hall", capacity=100)
    computer_lab = resolve_room_config("computer_lab", capacity=40)
    assert lecture_hall.num_acs >= 1
    assert computer_lab.num_acs >= 1
    assert lecture_hall.total_hvac_capacity_kw == lecture_hall.num_acs * lecture_hall.ac_unit_cooling_kw

def test_member3_resolve_room_config_respects_explicit_overrides():
    config = resolve_room_config("computer_lab", capacity=60, num_acs=10)
    assert config.capacity == 60
    assert config.num_acs == 10
    assert config.total_hvac_capacity_kw == 70.0  # 10 x 7 kW (24,000 BTU) units

def test_member3_resolve_room_config_unknown_type_falls_back_to_lecture_hall():
    config = resolve_room_config("spaceship_bridge", capacity=100)
    assert config.room_type == "lecture_hall"

def test_member3_room_type_labels_match_existing_campus_inventory():
    """These specific labels are already used in room_repository.py's seeded rooms
    (LH-1='Lecture Hall', AUD-1='Auditorium', LAB-3='Computer Lab') — picking an
    existing room and picking its type here must resolve to the same preset."""
    for label in ("Lecture Hall", "Auditorium", "Computer Lab"):
        key = label.strip().lower().replace(" ", "_")
        assert key in ROOM_TYPE_PRESETS

def test_member3_list_room_type_presets_is_serializable_for_the_api():
    presets = list_room_type_presets()
    assert len(presets) == len(ROOM_TYPE_PRESETS)
    for p in presets:
        assert set(p) >= {"key", "label", "capacity_options", "default_capacity", "suggested_ac_count", "ac_unit_cooling_kw"}

def test_member3_suggest_ac_count_scales_with_capacity():
    assert suggest_ac_count("computer_lab", 80) > suggest_ac_count("computer_lab", 20)

def test_member3_agent_resolves_hypothetical_room_and_reports_room_config():
    """The agent must actually USE the resolved room physics (not just echo the
    request back), and report room_config so the frontend can show what it assumed."""
    agent = DigitalTwinAgent()
    result = agent.execute({
        "initial_temp_c": 24.0,
        "ambient_temperatures_c": [30.0] * 6,
        "room_type": "computer_lab",
        "seating_capacity": 40,
        "num_acs": 4,
    }).data

    assert result["room_config"] is not None
    assert result["room_config"]["room_type"] == "computer_lab"
    assert result["room_config"]["capacity"] == 40
    assert result["room_config"]["num_acs"] == 4
    assert result["room_config"]["total_hvac_capacity_kw"] == 28.0
    # No occupancy was supplied — hypothetical-room mode defaults to full capacity.
    assert result["occupancy_counts"] == [40] * 6

def test_member3_agent_caps_supplied_occupancy_at_hypothetical_room_capacity():
    agent = DigitalTwinAgent()
    result = agent.execute({
        "initial_temp_c": 24.0,
        "ambient_temperatures_c": [28.0] * 3,
        "occupancy_counts": [500, 500, 500],
        "room_type": "seminar_room",
        "seating_capacity": 20,
    }).data
    assert result["occupancy_counts"] == [20, 20, 20]

def test_member3_agent_without_room_type_is_unaffected():
    """Callers that never mention room_type must behave exactly as before — this is
    the regression guard for the opt-in design."""
    agent = DigitalTwinAgent()
    result = agent.execute({
        "initial_temp_c": 24.0,
        "ambient_temperatures_c": [28.0] * 4,
        "occupancy_counts": [50] * 4,
    }).data
    assert result["room_config"] is None

def test_member3_agent_with_baseline_twin_injected_still_works_without_room_type():
    """Regression guard for the real bug this feature surfaced: the reference
    baseline's simulate() does not accept extra_heat_kw, so it must never be passed
    unless a room_type explicitly requests a twin this agent builds itself."""
    from src.infrastructure.reference_baselines.baseline_thermal import BaselineBuildingThermalTwin
    agent = DigitalTwinAgent(thermal_twin=BaselineBuildingThermalTwin())
    result = agent.execute({
        "initial_temp_c": 24.0,
        "ambient_temperatures_c": [28.0] * 4,
        "occupancy_counts": [50] * 4,
    })
    assert result.success is True, result.error

def test_member3_run_what_if_scenarios_accepts_room_config():
    agent = DigitalTwinAgent()
    results = agent.run_what_if_scenarios(
        initial_temp_c=24.0,
        ambient_temperatures_c=[30.0] * 6,
        occupancy_counts=[],
        room_type="auditorium",
        seating_capacity=400,
        num_acs=8,
    )
    for scenario in results.values():
        assert scenario["room_config"]["room_type"] == "auditorium"
        assert scenario["room_config"]["num_acs"] == 8

# -----------------------------------------------------------------------------
# Venue catalogue, operating hours and the occupied-hours simulation
# -----------------------------------------------------------------------------

def test_member3_weekday_operating_hours_are_0830_to_1730():
    hours = operating_hours_for(date(2026, 10, 1))  # a Thursday
    assert (hours.day_type, hours.start, hours.end) == ("weekday", "08:30", "17:30")
    mask = occupied_mask(hours)
    assert [i for i, m in enumerate(mask) if m] == list(range(17, 35))  # 08:30 .. 17:00 slots

def test_member3_weekend_operating_hours_are_0800_to_2000():
    for day in (date(2026, 10, 3), date(2026, 10, 4)):  # Saturday, Sunday
        hours = operating_hours_for(day)
        assert (hours.day_type, hours.start, hours.end) == ("weekend", "08:00", "20:00")
        assert [i for i, m in enumerate(occupied_mask(hours)) if m] == list(range(16, 40))

def test_member3_room_type_aliases_resolve_to_presets():
    assert preset_key_for("Laboratory") == "science_lab"
    assert preset_key_for("Library") == "study_area"
    assert preset_key_for("Drawing Room") == "drawing_room"
    assert preset_key_for("Gymnasium") is None

def test_member3_ac_suggestion_rounds_up():
    # 35 seats per unit: 70 seats is exactly 2 units, 71 needs a third — never size short.
    assert suggest_ac_count("lecture_hall", 70) == 2
    assert suggest_ac_count("lecture_hall", 71) == 3

def test_member3_every_seeded_room_type_has_a_preset():
    for room in SEED_ROOMS:
        assert preset_key_for(room["room_type"]) is not None, room

def test_member3_venue_catalogue_groups_rooms_by_type():
    catalogue = {t["key"]: t for t in build_venue_catalogue(SEED_ROOMS)}
    for key in ("lecture_hall", "computer_lab", "science_lab", "auditorium", "study_area", "drawing_room", "seminar_room"):
        assert catalogue[key]["rooms"], f"{key} should list at least one room"
    assert {r["room_id"] for r in catalogue["study_area"]["rooms"]} == {"STDY-1", "STDY-2", "STDY-3"}

def test_member3_venue_catalogue_keeps_rooms_of_an_unknown_type():
    catalogue = build_venue_catalogue([{"room_id": "GYM-1", "building_name": "Sports Complex", "room_type": "Gymnasium", "max_capacity": 90}])
    gym = next(t for t in catalogue if t["label"] == "Gymnasium")
    assert gym["rooms"][0]["room_id"] == "GYM-1"

def _occupied_run(num_acs, occ_multiplier=1.0, ambient=31.0, initial_temp=24.0):
    mask = occupied_mask(operating_hours_for(date(2026, 10, 1)))
    return DigitalTwinAgent().execute({
        "initial_temp_c": initial_temp,
        "ambient_temperatures_c": [ambient] * 48,
        "room_type": "lecture_hall",
        "seating_capacity": 150,
        "num_acs": num_acs,
        "occupied_mask": mask,
        "perturb_occ_multiplier": occ_multiplier,
    }).data, mask

def test_member3_room_is_empty_and_acs_off_outside_operating_hours():
    result, mask = _occupied_run(num_acs=6)
    assert result["hvac_mode"] == "occupied_thermostat"
    for i, open_ in enumerate(mask):
        if open_:
            assert result["occupancy_counts"][i] == 150
        else:
            assert result["occupancy_counts"][i] == 0
            assert result["hvac_power_kw"][i] == 0.0

def test_member3_comfort_is_only_judged_while_the_room_is_in_use():
    """The room starts the night warm (27 °C) with its ACs off, so the closed half-hours
    sit above 25.5 °C — that must not count. Enough cooling to pull it down in the first
    open half-hour means the occupied half-hours, the only ones assessed, stay comfortable."""
    result, mask = _occupied_run(num_acs=50, initial_temp=27.0)
    closed_temps = [t for t, open_ in zip(result["simulated_indoor_temps_c"], mask) if not open_]
    assert max(closed_temps) > 25.5, "setup: the closed room should get warm"
    assert result["assessed_intervals_count"] == sum(mask)
    assert result["comfort_violations_count"] == 0

def test_member3_too_few_acs_overheats_the_occupied_room():
    result, _ = _occupied_run(num_acs=1)
    assert result["comfort_violations_hot"] > 0
    assert result["is_thermal_feasible"] is False

def test_member3_crowd_surge_is_not_erased_by_the_seat_cap():
    result, mask = _occupied_run(num_acs=6, occ_multiplier=2.0)
    assert max(result["occupancy_counts"]) == 300  # 150 seats x 2

def test_member3_venues_endpoint_lists_types_rooms_and_hours(client):
    data = client.get("/api/simulation/venues").json()["data"]
    keys = [t["key"] for t in data["venue_types"]]
    assert keys[:7] == ["lecture_hall", "computer_lab", "science_lab", "auditorium", "study_area", "drawing_room", "seminar_room"]
    assert data["operating_hours"]["weekday"] == {"start": "08:30", "end": "17:30"}
    assert data["today"] == campus_today().isoformat()

def test_member3_what_if_listed_room_uses_its_type_and_hours(client):
    resp = client.post("/api/simulation/what-if", json={"room": "STDY-1"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["room"] == "STDY-1" and data["is_custom_room"] is False
    assert data["room_config"]["room_type"] == "study_area" and data["room_capacity"] == 150
    assert data["operating_hours"]["start"] in ("08:30", "08:00")

def test_member3_what_if_custom_room(client):
    resp = client.post("/api/simulation/what-if", json={"room_type": "drawing_room", "seating_capacity": 45, "num_acs": 3})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["room"] == "Custom Drawing Room" and data["is_custom_room"] is True
    assert data["room_config"]["capacity"] == 45 and data["room_config"]["num_acs"] == 3

def test_member3_what_if_unknown_room_is_404(client):
    assert client.post("/api/simulation/what-if", json={"room": "XX-99"}).status_code == 404

def test_member3_what_if_rejects_a_past_date_but_accepts_today(client):
    yesterday = (campus_today() - timedelta(days=1)).isoformat()
    assert client.post("/api/simulation/what-if", json={"date": yesterday}).status_code == 422
    assert client.post("/api/simulation/what-if", json={"date": campus_today().isoformat()}).status_code == 200

# -----------------------------------------------------------------------------
# Realistic room physics, energy/cost, pre-cooling
# -----------------------------------------------------------------------------

def test_member3_room_scale_constants_are_substepped_and_stable():
    """A real room's air responds in minutes, so one 30-minute Euler step would overshoot.
    The empty room warming towards a 30 °C ambient must rise monotonically and never
    overshoot it."""
    config = resolve_room_config("lecture_hall", capacity=150)
    twin = BuildingThermalTwin(c_in=config.c_in, r_vent=config.r_vent, c_wall=config.c_wall, r_in=config.r_in, r_out=config.r_out)
    assert twin._substeps(0.5) > 1
    temps = twin.simulate(initial_temp_c=24.0, ambient_temps=[30.0] * 48, occupant_counts=[0] * 48, hvac_power_kw=[0.0] * 48)
    assert all(b >= a for a, b in zip(temps, temps[1:]))
    assert max(temps) <= 30.0

def test_member3_building_scale_constants_need_no_substeps():
    assert BuildingThermalTwin()._substeps(0.5) == 1

def test_member3_room_time_constants_are_room_like():
    """Air follows within the hour; the structure over hours — not the days the old
    building-scale guess implied."""
    for key in ROOM_TYPE_PRESETS:
        c = resolve_room_config(key)
        tau_air = c.c_in / (1 / c.r_in + 1 / c.r_vent)
        tau_wall = c.c_wall / (1 / c.r_in + 1 / c.r_out)
        assert 0.05 < tau_air < 1.0, (key, tau_air)
        assert 2.0 < tau_wall < 24.0, (key, tau_wall)

def test_member3_energy_cost_uses_cop_and_time_of_use_rates():
    from src.agents.digital_twin.energy_cost import estimate_hvac_energy
    # 6.4 kW of cooling / COP 3.2 = 2 kW electric for two half-hours at 00:00 (off-peak LKR 15).
    energy = estimate_hvac_energy([6.4, 6.4] + [0.0] * 46)
    assert energy["electricity_kwh"] == 2.0
    assert energy["cost_lkr"] == 30.0
    assert energy["peak_electric_kw"] == 2.0 and energy["peak_time"] == "00:00"
    # The same draw at 19:00 is inside the 18:00-22:30 peak window (LKR 58).
    peak = estimate_hvac_energy([0.0] * 38 + [6.4] + [0.0] * 9)
    assert peak["cost_lkr"] == 58.0 and peak["peak_in_tariff_peak_window"] is True

def test_member3_room_simulation_reports_energy():
    result, _ = _occupied_run(num_acs=6)
    assert result["hvac_energy"]["electricity_kwh"] > 0
    assert result["hvac_energy"]["cost_lkr"] > 0

def test_member3_precool_starts_the_acs_before_opening_only():
    mask = occupied_mask(operating_hours_for(date(2026, 10, 1)))  # opens at slot 17 (08:30)
    result = DigitalTwinAgent().execute({
        "initial_temp_c": 27.0, "ambient_temperatures_c": [31.0] * 48,
        "room_type": "lecture_hall", "seating_capacity": 150, "num_acs": 6,
        "occupied_mask": mask, "precool_intervals": 2,
    }).data
    hvac = result["hvac_power_kw"]
    assert hvac[15] > 0 and hvac[16] > 0           # 07:30 and 08:00 — pre-cooling
    assert all(q == 0.0 for q in hvac[:15])        # nothing earlier
    assert result["occupancy_counts"][15] == 0      # nobody there yet
    assert result["assessed_intervals_count"] == sum(mask)  # pre-cool hours are not judged

def test_member3_what_if_precool_option(client):
    assert client.post("/api/simulation/what-if", json={"precool_minutes": 45}).status_code == 422
    resp = client.post("/api/simulation/what-if", json={"room": "LH-2", "precool_minutes": 60})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["precool_intervals"] == 2
    assert data["hvac_energy"]["cost_lkr"] > 0


# ---------------------------------------------------------------------------
# Review follow-up: series-length validation, solar gain, solar dropout,
# post-solve plan verification and MCP message integrity.
# ---------------------------------------------------------------------------

from src.agents.digital_twin.validation import SeriesLengthMismatchError
from src.agents.digital_twin.solar import clear_sky_irradiance_kw_m2, typical_irradiance_kw_m2
from src.agents.digital_twin.energy_cost import estimate_solar_shortfall
from src.agents.digital_twin.thermal_calibration import load_ambient_temperatures
from src.agents.digital_twin.mcp_integrity import MessageIntegrityGuard, sign_request
from src.agents.digital_twin.mcp_server import UNAUTHORIZED

_WEEKDAY = date(2026, 10, 1)


def _lecture_hall_day(**overrides):
    ambients = load_ambient_temperatures()
    return {
        "initial_temp_c": 24.0,
        "ambient_temperatures_c": ambients,
        "room_type": "lecture_hall",
        "seating_capacity": 100,
        "occupied_mask": occupied_mask(operating_hours_for(_WEEKDAY), len(ambients)),
        "date": _WEEKDAY.isoformat(),
        **overrides,
    }


def test_member3_thermal_model_rejects_mismatched_series():
    with pytest.raises(SeriesLengthMismatchError):
        BuildingThermalTwin().simulate(24.0, [30.0] * 3, [10] * 2, [0.0] * 3)
    with pytest.raises(SeriesLengthMismatchError):
        BuildingThermalTwin().simulate(24.0, [30.0] * 3, [10] * 3, [0.0] * 3, solar_gain_kw=[1.0] * 2)


def test_member3_battery_rejects_mismatched_plans():
    with pytest.raises(SeriesLengthMismatchError):
        BatteryDynamicsModel().simulate_soc_trajectory(250.0, [10.0] * 48, [0.0] * 47)


def test_member3_agent_fails_cleanly_on_mismatched_series():
    """The agent must refuse a short occupancy or battery plan with a readable error,
    not simulate a truncated day."""
    agent = DigitalTwinAgent()
    short_occ = agent.execute({"ambient_temperatures_c": [28.0] * 48, "occupancy_counts": [50] * 24})
    short_battery = agent.execute({
        "ambient_temperatures_c": [28.0] * 48, "occupancy_counts": [50] * 48,
        "battery_charge_kw": [0.0] * 47, "battery_discharge_kw": [0.0] * 47,
    })
    for res in (short_occ, short_battery):
        assert res.success is False
        assert "SERIES_LENGTH_MISMATCH" in res.error


def test_member3_irradiance_follows_the_sun():
    g = clear_sky_irradiance_kw_m2(_WEEKDAY)
    assert len(g) == 48
    assert all(v == 0.0 for v in g[:10]) and all(v == 0.0 for v in g[40:]), "No sun before 05:00 or after 20:00"
    peak = max(range(48), key=lambda i: g[i])
    assert 22 <= peak <= 25, "Peak near solar noon (~12:10 in Colombo)"
    assert 0.9 < g[peak] < 1.1, "Near-overhead tropical sun, clear sky"
    typical = typical_irradiance_kw_m2(_WEEKDAY)
    assert max(typical) < g[peak]


def test_member3_solar_gain_warms_a_room_and_costs_cooling():
    agent = DigitalTwinAgent()
    sunny = agent.execute(_lecture_hall_day()).data
    dark = agent.execute(_lecture_hall_day(solar_irradiance_kw_m2=[0.0] * 48)).data
    assert max(sunny["solar_gain_kw"]) > 1.0
    assert sunny["room_config"]["solar_aperture_m2"] > 0
    assert sunny["hvac_energy"]["electricity_kwh"] > dark["hvac_energy"]["electricity_kwh"]


def test_member3_solar_dropout_cuts_sunshine_not_air_conditioning():
    """Review finding: the dropout used to derate the ACs. It must now reduce PV generation
    and solar heat gain, and leave the AC capacity untouched."""
    agent = DigitalTwinAgent()
    solar = [0.0] * 12 + [200.0] * 24 + [0.0] * 12
    demand = [300.0] * 48
    results = agent.run_what_if_scenarios(
        initial_temp_c=24.0,
        ambient_temperatures_c=load_ambient_temperatures(),
        occupancy_counts=[],
        room_type="lecture_hall", seating_capacity=100,
        occupied_mask=occupied_mask(operating_hours_for(_WEEKDAY), 48),
        simulation_date=_WEEKDAY, forecast_solar_kw=solar, forecast_demand_kw=demand,
    )
    baseline = agent.execute(_lecture_hall_day(forecast_solar_kw=solar, forecast_demand_kw=demand)).data
    dropout = results["solar_dropout"]

    assert dropout["room_config"]["total_hvac_capacity_kw"] == baseline["room_config"]["total_hvac_capacity_kw"]
    assert max(dropout["hvac_power_kw"]) <= dropout["room_config"]["total_hvac_capacity_kw"]
    assert sum(dropout["solar_gain_kw"]) == pytest.approx(0.5 * sum(baseline["solar_gain_kw"]), rel=0.01)

    supply = dropout["solar_supply"]
    assert supply["forecast_solar_kw"] == [s * 0.5 for s in solar]
    assert supply["pv_energy_lost_kwh"] == pytest.approx(0.5 * sum(solar) * 0.5)
    assert supply["extra_grid_import_kwh"] == pytest.approx(supply["pv_energy_lost_kwh"])
    assert supply["extra_grid_cost_lkr"] > 0
    assert baseline["solar_supply"]["pv_energy_lost_kwh"] == 0


def test_member3_solar_shortfall_only_counts_demand_actually_unmet():
    """PV beyond demand was never offsetting anything, so losing it costs no extra import."""
    out = estimate_solar_shortfall([100.0, 100.0], 0.5, forecast_demand_kw=[20.0, 20.0])
    assert out["pv_energy_lost_kwh"] == 50.0
    assert out["extra_grid_import_kwh"] == 0.0


def _plan(n=48, charge=0.0, discharge=0.0, **battery):
    return {
        "solver_output": {"battery_charge_kw": [charge] * n, "battery_discharge_kw": [discharge] * n},
        "battery_parameters": {"battery_capacity_kwh": 500.0, "max_charge_rate_kw": 100.0,
                               "max_discharge_rate_kw": 100.0, "initial_soc_ratio": 0.5, **battery},
    }


def test_member3_verify_plan_accepts_a_feasible_plan():
    check = DigitalTwinAgent().verify_dispatch_plan(_lecture_hall_day(), _plan())
    assert check["verdict"] == "accept", check["reasons"]
    assert check["checks"]["battery_soc_violations"] == 0


def test_member3_verify_plan_sends_battery_breaches_back_to_the_optimizer():
    plan = _plan()
    plan["solver_output"]["battery_charge_kw"][3] = 150.0      # above the 100 kW limit
    plan["solver_output"]["battery_discharge_kw"][3] = 20.0    # and at the same time as charging
    plan["solver_output"]["battery_discharge_kw"][30:48] = [100.0] * 18  # drains below 20% SOC
    check = DigitalTwinAgent().verify_dispatch_plan(_lecture_hall_day(), plan)
    assert check["verdict"] == "re_optimize"
    assert check["checks"]["charge_limit_breaches"] == 1
    assert check["checks"]["simultaneous_charge_discharge"] == 1
    assert check["checks"]["battery_soc_violations"] > 0


def test_member3_verify_plan_rejects_a_day_no_plan_can_keep_comfortable():
    day = _lecture_hall_day(num_acs=1, perturb_temp_delta_c=8.0)
    check = DigitalTwinAgent().verify_dispatch_plan(day, _plan())
    assert check["verdict"] == "reject"
    assert check["checks"]["comfort_fixable_by_hvac"] is False


def test_member3_verify_plan_rejects_a_plan_of_the_wrong_length():
    check = DigitalTwinAgent().verify_dispatch_plan(_lecture_hall_day(), _plan(n=24))
    assert check["verdict"] == "reject"
    assert "SERIES_LENGTH_MISMATCH" in check["reasons"][0]


def test_member3_verify_plan_flags_solver_soc_disagreement():
    plan = _plan()
    plan["solver_output"]["battery_soc_kwh"] = [400.0] * 48  # the idle battery stays at 250
    check = DigitalTwinAgent().verify_dispatch_plan(_lecture_hall_day(), plan)
    assert check["verdict"] == "re_optimize"
    assert check["checks"]["max_soc_gap_vs_solver_kwh"] == 150.0


_KEYS = {"agent2": "unit-test-secret"}
_LIST = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}


def test_member3_integrity_rejects_stale_and_future_messages():
    now = [1_000_000.0]
    server = create_digital_twin_mcp_server(MessageIntegrityGuard(_KEYS, clock=lambda: now[0]))
    stale = sign_request(_LIST, "agent2", _KEYS["agent2"], timestamp=int(now[0]) - 301)
    future = sign_request(_LIST, "agent2", _KEYS["agent2"], timestamp=int(now[0]) + 301)
    fresh = sign_request(_LIST, "agent2", _KEYS["agent2"], timestamp=int(now[0]) - 299)
    assert "window" in server.handle_request(stale)["error"]["message"]
    assert "window" in server.handle_request(future)["error"]["message"]
    assert "result" in server.handle_request(fresh)


def test_member3_integrity_rejects_wrong_or_unknown_keys():
    server = create_digital_twin_mcp_server(MessageIntegrityGuard(_KEYS))
    forged = sign_request(_LIST, "agent2", "guessed-secret")
    unknown = sign_request(_LIST, "intruder", "whatever")
    assert server.handle_request(forged)["error"]["code"] == UNAUTHORIZED
    assert "unknown signing key" in server.handle_request(unknown)["error"]["message"]


def test_member3_integrity_rejects_a_tampered_method_and_malformed_blocks():
    server = create_digital_twin_mcp_server(MessageIntegrityGuard(_KEYS))
    signed = sign_request(_LIST, "agent2", _KEYS["agent2"])
    signed["method"] = "tools/call"
    assert server.handle_request(signed)["error"]["code"] == UNAUTHORIZED

    malformed = sign_request(_LIST, "agent2", _KEYS["agent2"])
    malformed["params"]["_meta"]["campusgrid/integrity"]["timestamp"] = "yesterday"
    assert "malformed" in server.handle_request(malformed)["error"]["message"]


def test_member3_integrity_forgets_nonces_only_after_they_expire():
    now = [1_000_000.0]
    guard = MessageIntegrityGuard(_KEYS, clock=lambda: now[0])
    msg = sign_request(_LIST, "agent2", _KEYS["agent2"], timestamp=int(now[0]), nonce="n-1")
    assert guard.verify(msg) is None
    now[0] += 200
    assert "replay" in guard.verify(msg)
    now[0] += 200  # past the window: the nonce is forgotten, but the timestamp now fails instead
    assert "window" in guard.verify(msg)


def test_member3_integrity_fails_closed_when_the_nonce_table_is_full():
    guard = MessageIntegrityGuard(_KEYS, max_tracked_nonces=2)
    for i in range(2):
        assert guard.verify(sign_request(_LIST, "agent2", _KEYS["agent2"], nonce=f"n{i}")) is None
    assert "too many" in guard.verify(sign_request(_LIST, "agent2", _KEYS["agent2"], nonce="n2"))


def test_member3_unsigned_notification_is_dropped_silently_when_signing_is_required():
    server = create_digital_twin_mcp_server(MessageIntegrityGuard(_KEYS))
    assert server.handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert server.requires_signed_messages is True
    assert create_digital_twin_mcp_server().requires_signed_messages is False
