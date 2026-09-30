"""
CampusGrid AI: Agent 2 — Digital Twin Simulation (Physics · Simulation)
Executes 2R2C building thermal physics, evaluates ASHRAE-55 comfort, and validates battery SOC envelopes.
Runs what-if environmental and crowd perturbation simulations.
"""

import math
from datetime import date
from typing import Dict, Any, List, Optional, Union
from src.agents.base.agent import BaseAgent
from src.agents.digital_twin.thermal_model import BuildingThermalTwin
from src.domain.interfaces.tool import Tool
from src.domain.interfaces.thermal_twin import BuildingThermalTwinInterface, BatteryDynamicsInterface
from src.agents.digital_twin.battery_dynamics import BatteryDynamicsModel
from src.agents.digital_twin.room_presets import resolve_room_config
from src.agents.digital_twin.energy_cost import estimate_hvac_energy, estimate_solar_shortfall
from src.agents.digital_twin.solar import solar_heat_gain_kw, typical_irradiance_kw_m2
from src.agents.digital_twin.validation import require_equal_lengths
from src.shared.constants import (
    COMFORT_TEMP_MIN_C,
    COMFORT_TEMP_MAX_C,
    COMFORT_SETPOINT_DEFAULT_C,
    BATTERY_CAPACITY_DEFAULT_KWH,
)
from src.shared.datetime_utils import campus_today

# Rated cooling one zone can draw when a setpoint is controlled (kW thermal). Settings override it.
DEFAULT_HVAC_MAX_COOLING_KW = 35.0
_THERMOSTAT_BISECTION_STEPS = 20
# Slack when comparing the twin's battery trajectory with the solver's: both round to 0.01 kWh
# per interval, so rounding alone can drift them apart by a few hundredths over a day.
_SOC_AGREEMENT_TOLERANCE_KWH = 0.5


def _as_date(value: Union[str, date, None]) -> date:
    """The simulated day (for the sun's path): an ISO string, a date, or today on campus."""
    if value is None:
        return campus_today()
    return value if isinstance(value, date) else date.fromisoformat(str(value))

class DigitalTwinAgent(BaseAgent):
    """Agent 2: Cyber-physical simulator validating feasibility and what-if scenarios."""

    def __init__(
        self,
        simulation_tool: Optional[Tool] = None,
        thermal_twin: Optional[BuildingThermalTwinInterface] = None,
        battery_dynamics: Optional[BatteryDynamicsInterface] = None,
        comfort_min_c: float = COMFORT_TEMP_MIN_C,
        comfort_max_c: float = COMFORT_TEMP_MAX_C,
        battery_capacity_kwh: float = BATTERY_CAPACITY_DEFAULT_KWH,
        hvac_max_cooling_kw: float = DEFAULT_HVAC_MAX_COOLING_KW,
    ):
        super().__init__(
            name="Agent 2: Digital Twin Simulation",
            description="Solves 2R2C grey-box differential equations and checks physical feasibility."
        )
        self.simulation_tool = simulation_tool
        self.thermal_twin = thermal_twin or BuildingThermalTwin()
        self.battery_dynamics = battery_dynamics or BatteryDynamicsModel()
        # Defaults come from the container (settings); a caller may override them per request.
        self.comfort_min_c = comfort_min_c
        self.comfort_max_c = comfort_max_c
        self.battery_capacity_kwh = battery_capacity_kwh
        self.hvac_max_cooling_kw = hvac_max_cooling_kw

    def _run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        initial_temp = float(input_data.get("initial_temp_c", 24.0))
        ambient_temps = input_data.get("ambient_temperatures_c", [])
        occupants = input_data.get("occupancy_counts", [])
        hvac_proposal = input_data.get("hvac_power_kw", [])

        # Apply perturbation if requested (What-If analysis)
        temp_delta = float(input_data.get("perturb_temp_delta_c", 0.0))
        occ_multiplier = float(input_data.get("perturb_occ_multiplier", 1.0))
        # Fraction of the forecast sunshine that actually arrives. A solar dropout (cloud,
        # monsoon) lowers it below 1.0, which cuts both the PV generation the campus can
        # use (forecast_solar_kw) and the sun's heat through a room's windows. It does NOT
        # touch the ACs: they run on grid and battery power whatever the sky does.
        solar_scaling_factor = float(input_data.get("perturb_solar_scaling_factor", 1.0))
        if not 0.0 <= solar_scaling_factor <= 1.0:
            raise ValueError("perturb_solar_scaling_factor must be between 0 and 1")

        perturbed_ambients = [round(t + temp_delta, 2) for t in ambient_temps]
        n_intervals = len(perturbed_ambients)
        setpoint = input_data.get("target_setpoint_c")

        # Operating hours (see operating_hours.py): True where the room is open. When given,
        # people, equipment and ACs are only present while it is open, and comfort is only
        # judged while it is occupied — an empty room drifting warm overnight is not a
        # comfort violation.
        occupied_mask: Optional[List[bool]] = input_data.get("occupied_mask")
        if occupied_mask is not None:
            occupied_mask = [bool(m) for m in occupied_mask]

        # Every per-interval series must cover the same horizon as the weather: a short one
        # used to be silently truncated by zip() further down. Empty lists mean "not supplied".
        forecast_solar_kw = input_data.get("forecast_solar_kw")
        forecast_demand_kw = input_data.get("forecast_demand_kw")
        require_equal_lengths(
            ambient_temperatures_c=perturbed_ambients,
            occupancy_counts=occupants or None,
            hvac_power_kw=hvac_proposal or None,
            occupied_mask=occupied_mask,
            battery_charge_kw=input_data.get("battery_charge_kw"),
            battery_discharge_kw=input_data.get("battery_discharge_kw"),
            solar_irradiance_kw_m2=input_data.get("solar_irradiance_kw_m2"),
            solar_gain_kw=input_data.get("solar_gain_kw"),
            forecast_solar_kw=forecast_solar_kw,
            forecast_demand_kw=forecast_demand_kw,
        )

        # Pre-cooling: the ACs may start this many half-hours before each opening, pulling
        # heat out of the room's structure before people arrive. Comfort is still judged
        # only while the room is occupied.
        precool_intervals = max(0, int(input_data.get("precool_intervals") or 0))
        ac_mask: Optional[List[bool]] = None
        if occupied_mask is not None:
            ac_mask = list(occupied_mask)
            for i, open_ in enumerate(occupied_mask):
                if open_ and (i == 0 or not occupied_mask[i - 1]):
                    for j in range(max(0, i - precool_intervals), i):
                        ac_mask[j] = True

        # Room configuration: a venue type + seating capacity + AC count, either a room
        # listed in the campus inventory or a custom one (see room_presets.py). Opt-in —
        # omitting all three keeps every existing caller on the injected thermal_twin
        # (the calibrated building constants, or its reference baseline), unchanged.
        room_config = None
        room_type = input_data.get("room_type")
        seating_capacity = input_data.get("seating_capacity")
        num_acs = input_data.get("num_acs")
        # `extra_heat_kw` is only accepted by MY BuildingThermalTwin (thermal_model.py),
        # not by BuildingThermalTwinInterface generally — the reference baseline predates
        # it and does not take this kwarg. It is only ever passed to a twin THIS method
        # constructs itself (the room-config branch below), never to an injected
        # self.thermal_twin, which might be the baseline.
        active_extra_heat_kw: Optional[List[float]] = None
        # Q_solar follows the same rule: computed for a room this method builds (its glazing
        # is known from the preset), or taken as given when a caller supplies it explicitly.
        irradiance_kw_m2: Optional[List[float]] = None
        active_solar_gain_kw: Optional[List[float]] = None
        if input_data.get("solar_gain_kw") is not None:
            active_solar_gain_kw = [round(float(q) * solar_scaling_factor, 3) for q in input_data["solar_gain_kw"]]
        if room_type or seating_capacity or num_acs:
            room_config = resolve_room_config(room_type, seating_capacity, num_acs)
            active_thermal_twin = BuildingThermalTwin(
                c_in=room_config.c_in, r_vent=room_config.r_vent,
                c_wall=room_config.c_wall, r_in=room_config.r_in, r_out=room_config.r_out,
            )
            active_hvac_ceiling_kw = room_config.total_hvac_capacity_kw
            if occupied_mask is not None:
                active_extra_heat_kw = [room_config.equipment_heat_kw if occ else 0.0 for occ in occupied_mask]
            else:
                active_extra_heat_kw = [room_config.equipment_heat_kw] * n_intervals
            if active_solar_gain_kw is None:
                if input_data.get("solar_irradiance_kw_m2") is not None:
                    base_irradiance = [float(g) for g in input_data["solar_irradiance_kw_m2"]]
                else:
                    base_irradiance = typical_irradiance_kw_m2(_as_date(input_data.get("date")), n_intervals)
                irradiance_kw_m2 = [round(g * solar_scaling_factor, 4) for g in base_irradiance]
                # The sun heats the room whether or not anyone is in it.
                active_solar_gain_kw = solar_heat_gain_kw(irradiance_kw_m2, room_config.solar_aperture_m2)
            # Supplied headcounts (e.g. building-wide meter counts) are capped at the room's
            # seats; otherwise the room is full while open. The occupancy multiplier applies
            # after the cap, so a "crowd surge" can still push a room past its seat count.
            if occupants:
                base_occupants = [min(o, room_config.capacity) for o in occupants]
            elif occupied_mask is not None:
                base_occupants = [room_config.capacity if occ else 0 for occ in occupied_mask]
            else:
                base_occupants = [room_config.capacity] * n_intervals
        else:
            active_thermal_twin = self.thermal_twin
            active_hvac_ceiling_kw = self.hvac_max_cooling_kw
            base_occupants = occupants
        perturbed_occupants = [int(o * occ_multiplier) for o in base_occupants]

        # Heat series only MY BuildingThermalTwin accepts (see the note on extra_heat_kw).
        sim_kwargs: Dict[str, Any] = {}
        if active_extra_heat_kw is not None:
            sim_kwargs["extra_heat_kw"] = active_extra_heat_kw
        if active_solar_gain_kw is not None:
            sim_kwargs["solar_gain_kw"] = active_solar_gain_kw

        if hvac_proposal:
            hvac_mode = "supplied"
            hvac_proposal = [round(float(p), 2) for p in hvac_proposal]
        elif setpoint is not None or occupied_mask is not None:
            # Thermostat: cool towards the setpoint within the plant capacity — and, when
            # operating hours are known, only while the room is open (ACs off otherwise).
            hvac_mode = "occupied_thermostat" if occupied_mask is not None else "thermostat"
            if setpoint is None:
                setpoint = COMFORT_SETPOINT_DEFAULT_C
            ceiling_kw = active_hvac_ceiling_kw
            hvac_proposal = self._thermostat_schedule(
                initial_temp, perturbed_ambients, perturbed_occupants, float(setpoint), ceiling_kw,
                thermal_twin=active_thermal_twin, heat_series_kw=sim_kwargs,
                max_cooling_by_interval=(
                    [ceiling_kw if on else 0.0 for on in ac_mask] if ac_mask is not None else None
                ),
            )
        else:
            # No plan and no setpoint: standard office-hours cooling curve, capped at
            # whatever plant capacity is actually available (the room's ACs, if given).
            hvac_mode = "default_schedule"
            hvac_proposal = [
                round(min(35.0, active_hvac_ceiling_kw), 2)
                if (8 <= (i // 2) <= 17) else round(min(5.0, active_hvac_ceiling_kw), 2)
                for i in range(n_intervals)
            ]

        # Run 2R2C continuous thermal model
        indoor_temps = active_thermal_twin.simulate(
            initial_temp_c=initial_temp,
            ambient_temps=perturbed_ambients,
            occupant_counts=perturbed_occupants,
            hvac_power_kw=hvac_proposal,
            **sim_kwargs,
        )

        comfort_min = float(input_data.get("comfort_min_c", self.comfort_min_c))
        comfort_max = float(input_data.get("comfort_max_c", self.comfort_max_c))
        too_hot = too_cold = assessed = 0
        max_deviation_c = 0.0
        for i, t in enumerate(indoor_temps):
            if occupied_mask is not None and not occupied_mask[i]:
                continue
            assessed += 1
            if t > comfort_max:
                too_hot += 1
                max_deviation_c = max(max_deviation_c, t - comfort_max)
            elif t < comfort_min:
                too_cold += 1
                max_deviation_c = max(max_deviation_c, comfort_min - t)
        comfort_violations = too_hot + too_cold
        is_feasible = (comfort_violations == 0)

        # Battery safety check. Callers that only care about thermal feasibility (e.g.
        # the existing what-if API route) do not supply a charge/discharge plan — default
        # to an idle battery (no activity) so the SOC trajectory is still returned, flat
        # and violation-free, rather than silently skipped.
        battery_capacity_kwh = self.battery_capacity_kwh
        battery_initial_soc_kwh = float(
            input_data.get("battery_initial_soc_kwh", battery_capacity_kwh * 0.5)
        )
        battery_charge_kw = input_data.get("battery_charge_kw", [0.0] * n_intervals)
        battery_discharge_kw = input_data.get("battery_discharge_kw", [0.0] * n_intervals)

        battery_soc_trajectory_kwh, battery_soc_violations_count = self.battery_dynamics.simulate_soc_trajectory(
            initial_soc_kwh=battery_initial_soc_kwh,
            charge_kw_series=battery_charge_kw,
            discharge_kw_series=battery_discharge_kw,
        )
        is_battery_feasible = (battery_soc_violations_count == 0)

        return {
            "initial_temperature_c": initial_temp,
            "simulated_indoor_temps_c": indoor_temps,
            "ambient_temperatures_c": perturbed_ambients,
            "occupancy_counts": perturbed_occupants,
            "hvac_power_kw": hvac_proposal,
            "hvac_mode": hvac_mode,
            "target_setpoint_c": setpoint,
            "comfort_violations_count": comfort_violations,
            "comfort_violations_hot": too_hot,
            "comfort_violations_cold": too_cold,
            "assessed_intervals_count": assessed,
            "occupied_mask": occupied_mask,
            "precool_intervals": precool_intervals,
            # What running the ACs costs — reported for a room simulation, where the AC
            # count is known; the building-level planning pipeline prices energy in Agent 4.
            "hvac_energy": estimate_hvac_energy(hvac_proposal) if room_config is not None else None,
            "solar_irradiance_kw_m2": irradiance_kw_m2,
            "solar_gain_kw": active_solar_gain_kw,
            # A solar dropout's effect on supply: the reduced PV series (for re-running battery
            # dispatch against it), the energy lost and, with a demand forecast, the extra grid
            # import. Only when the caller passes the PV forecast.
            "solar_supply": (
                estimate_solar_shortfall(forecast_solar_kw, solar_scaling_factor, forecast_demand_kw)
                if forecast_solar_kw is not None else None
            ),
            "is_thermal_feasible": is_feasible,
            "max_temp_deviation_c": round(max_deviation_c, 2),
            "comfort_limits": {"min_c": comfort_min, "max_c": comfort_max},
            "battery_soc_trajectory_kwh": battery_soc_trajectory_kwh,
            "battery_soc_violations_count": battery_soc_violations_count,
            "is_battery_feasible": is_battery_feasible,
            "perturbation_applied": {
                "temp_delta_c": temp_delta,
                "occupancy_multiplier": occ_multiplier,
                "solar_scaling_factor": solar_scaling_factor
            },
            "room_config": (
                {
                    "room_type": room_config.room_type,
                    "label": room_config.label,
                    "capacity": room_config.capacity,
                    "num_acs": room_config.num_acs,
                    "ac_unit_cooling_kw": room_config.ac_unit_cooling_kw,
                    "total_hvac_capacity_kw": room_config.total_hvac_capacity_kw,
                    "equipment_heat_kw": room_config.equipment_heat_kw,
                    "solar_aperture_m2": room_config.solar_aperture_m2,
                    "c_in": room_config.c_in,
                    "r_vent": room_config.r_vent,
                    "c_wall": room_config.c_wall,
                    "r_in": room_config.r_in,
                    "r_out": room_config.r_out,
                }
                if room_config is not None else None
            ),
        }

    def _thermostat_schedule(
        self,
        initial_temp: float,
        ambients: List[float],
        occupants: List[int],
        setpoint: float,
        max_cooling_kw: float,
        thermal_twin: Optional[BuildingThermalTwinInterface] = None,
        heat_series_kw: Optional[Dict[str, List[float]]] = None,
        max_cooling_by_interval: Optional[List[float]] = None,
    ) -> List[float]:
        """Per interval, the least cooling that keeps the room at or below the setpoint.

        Found by bisection on the active twin (injected member/baseline, or a per-request
        twin built from a room preset), re-simulating the whole prefix each time so any
        hidden state (e.g. the 2R2C wall temperature) carries over. Where even full
        capacity cannot hold the setpoint, the plant runs flat out. `max_cooling_by_interval`
        overrides the capacity per interval — 0 means the ACs are off (room closed).
        `heat_series_kw` holds the extra simulate() series (extra_heat_kw, solar_gain_kw).
        """
        twin = thermal_twin or self.thermal_twin
        heat_series_kw = heat_series_kw or {}

        schedule: List[float] = []
        for t in range(len(ambients)):
            cap_kw = max_cooling_by_interval[t] if max_cooling_by_interval is not None else max_cooling_kw
            if cap_kw <= 0:
                schedule.append(0.0)
                continue
            sim_kwargs = {name: series[: t + 1] for name, series in heat_series_kw.items()}

            def end_temp(q_kw: float) -> float:
                return twin.simulate(
                    initial_temp_c=initial_temp,
                    ambient_temps=ambients[: t + 1],
                    occupant_counts=occupants[: t + 1],
                    hvac_power_kw=schedule + [q_kw],
                    **sim_kwargs,
                )[-1]

            if end_temp(0.0) <= setpoint:
                schedule.append(0.0)
                continue
            if end_temp(cap_kw) > setpoint:
                schedule.append(round(cap_kw, 2))
                continue
            low, high = 0.0, cap_kw
            for _ in range(_THERMOSTAT_BISECTION_STEPS):
                mid = (low + high) / 2.0
                if end_temp(mid) > setpoint:
                    low = mid
                else:
                    high = mid
            schedule.append(math.ceil(high * 100.0) / 100.0)  # round up: never less cooling than needed
        return schedule

    def run_what_if_scenarios(
        self,
        initial_temp_c: float,
        ambient_temperatures_c: List[float],
        occupancy_counts: List[int],
        hvac_power_kw: Optional[List[float]] = None,
        battery_initial_soc_kwh: Optional[float] = None,
        battery_charge_kw: Optional[List[float]] = None,
        battery_discharge_kw: Optional[List[float]] = None,
        room_type: Optional[str] = None,
        seating_capacity: Optional[int] = None,
        num_acs: Optional[int] = None,
        occupied_mask: Optional[List[bool]] = None,
        precool_intervals: Optional[int] = None,
        simulation_date: Union[str, date, None] = None,
        forecast_solar_kw: Optional[List[float]] = None,
        forecast_demand_kw: Optional[List[float]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Runs the three required what-if scenarios against one baseline forecast:
        a heatwave, a crowd surge, and a solar dropout. Each result reports whether the
        building stays inside the comfort band and the battery stays inside its SOC
        band, and if not, by how much either misses.

        The solar dropout halves the sunshine: PV generation (reported in `solar_supply`
        when `forecast_solar_kw` is given, as the reduced series to re-dispatch against)
        and a room's solar heat gain. Air-conditioning capacity is unchanged."""
        baseline = {
            "initial_temp_c": initial_temp_c,
            "ambient_temperatures_c": ambient_temperatures_c,
            "occupancy_counts": occupancy_counts,
            "hvac_power_kw": hvac_power_kw or [],
        }
        optional = {
            "battery_initial_soc_kwh": battery_initial_soc_kwh,
            "battery_charge_kw": battery_charge_kw,
            "battery_discharge_kw": battery_discharge_kw,
            "room_type": room_type,
            "seating_capacity": seating_capacity,
            "num_acs": num_acs,
            "occupied_mask": occupied_mask,
            "precool_intervals": precool_intervals,
            "date": simulation_date,
            "forecast_solar_kw": forecast_solar_kw,
            "forecast_demand_kw": forecast_demand_kw,
        }
        baseline.update({k: v for k, v in optional.items() if v is not None})

        scenarios = {
            "heatwave": {**baseline, "perturb_temp_delta_c": 4.0},
            "crowd_surge": {**baseline, "perturb_occ_multiplier": 2.0},
            "solar_dropout": {**baseline, "perturb_solar_scaling_factor": 0.5},
        }

        return {
            scenario_name: self._run(scenario_input)
            for scenario_name, scenario_input in scenarios.items()
        }

    def verify_dispatch_plan(
        self,
        simulation_input: Dict[str, Any],
        dispatch_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Post-solve check: re-runs the digital twin on the plan Agent 4 actually produced.

        `simulation_input` is the same input this agent was given before optimization
        (weather, occupancy, room, ...). `dispatch_result` is Agent 4's output (its
        `solver_output` and `battery_parameters`), or a bare solver output. The battery
        schedule is simulated with the battery the plan was solved for; an HVAC schedule is
        simulated too if the plan carries one (`hvac_power_kw`), else the thermostat is.

        Returns a verdict the coordinator can act on:
          - "accept":      the plan is physically feasible.
          - "re_optimize": the plan breaks a limit that a different plan could meet
                           (battery power/SOC limits, or comfort that full AC could hold).
          - "reject":      the day is infeasible whatever the plan (comfort fails even with
                           every AC at full power), or the plan cannot be simulated at all.
        """
        solver = dispatch_result.get("solver_output") or dispatch_result
        battery = dispatch_result.get("battery_parameters") or {}
        charge = [float(x) for x in solver.get("battery_charge_kw") or []]
        discharge = [float(x) for x in solver.get("battery_discharge_kw") or []]

        default_battery = self.battery_dynamics if isinstance(self.battery_dynamics, BatteryDynamicsModel) else BatteryDynamicsModel()
        capacity_kwh = float(battery.get("battery_capacity_kwh", default_battery.capacity_kwh))
        max_charge_kw = float(battery.get("max_charge_rate_kw", default_battery.max_power_kw))
        max_discharge_kw = float(battery.get("max_discharge_rate_kw", default_battery.max_power_kw))
        plan_battery = BatteryDynamicsModel(
            capacity_kwh=capacity_kwh,
            max_power_kw=max(max_charge_kw, max_discharge_kw),
            min_soc_pct=default_battery.min_soc_pct,
            max_soc_pct=default_battery.max_soc_pct,
            round_trip_eff=default_battery.round_trip_eff,
        )
        twin = DigitalTwinAgent(
            simulation_tool=self.simulation_tool, thermal_twin=self.thermal_twin, battery_dynamics=plan_battery,
            comfort_min_c=self.comfort_min_c, comfort_max_c=self.comfort_max_c,
            battery_capacity_kwh=capacity_kwh, hvac_max_cooling_kw=self.hvac_max_cooling_kw,
        )

        plan_input = {
            **simulation_input,
            "battery_charge_kw": charge,
            "battery_discharge_kw": discharge,
            "battery_initial_soc_kwh": capacity_kwh * float(battery.get("initial_soc_ratio", 0.5)),
        }
        plan_has_hvac = bool(solver.get("hvac_power_kw"))
        if plan_has_hvac:
            plan_input["hvac_power_kw"] = [float(x) for x in solver["hvac_power_kw"]]

        run = twin.execute(plan_input)
        if not run.success:
            return {"verdict": "reject", "reasons": [f"The plan could not be simulated: {run.error}"],
                    "checks": {}, "simulation": None}
        sim = run.data

        eps = 1e-6
        over_charge = [i for i, c in enumerate(charge) if c > max_charge_kw + eps]
        over_discharge = [i for i, d in enumerate(discharge) if d > max_discharge_kw + eps]
        simultaneous = [i for i, (c, d) in enumerate(zip(charge, discharge)) if c > eps and d > eps]
        solver_soc = [float(x) for x in solver.get("battery_soc_kwh") or []]
        soc_gap_kwh = (
            round(max(abs(a - b) for a, b in zip(sim["battery_soc_trajectory_kwh"], solver_soc)), 2)
            if solver_soc and len(solver_soc) == len(charge) else None
        )

        reasons: List[str] = []
        if sim["battery_soc_violations_count"]:
            reasons.append(f"Battery leaves its state-of-charge band in {sim['battery_soc_violations_count']} interval(s).")
        if over_charge:
            reasons.append(f"Charging exceeds {max_charge_kw:g} kW in {len(over_charge)} interval(s).")
        if over_discharge:
            reasons.append(f"Discharging exceeds {max_discharge_kw:g} kW in {len(over_discharge)} interval(s).")
        if simultaneous:
            reasons.append(f"Battery charges and discharges at once in {len(simultaneous)} interval(s).")
        if soc_gap_kwh is not None and soc_gap_kwh > _SOC_AGREEMENT_TOLERANCE_KWH:
            reasons.append(f"The solver's state of charge differs from the simulated battery by up to {soc_gap_kwh:g} kWh.")
        battery_ok = not reasons

        comfort_ok = bool(sim["is_thermal_feasible"])
        comfort_fixable: Optional[bool] = None
        if not comfort_ok:
            # Could any HVAC schedule have held comfort? Re-run with the thermostat at full
            # capacity: if even that fails, no plan can fix the day.
            best_effort = {k: v for k, v in plan_input.items() if k != "hvac_power_kw"}
            best_effort.setdefault("target_setpoint_c", COMFORT_SETPOINT_DEFAULT_C)
            best = twin.execute(best_effort)
            comfort_fixable = bool(best.success and best.data["is_thermal_feasible"])
            reasons.append(
                f"Comfort band broken in {sim['comfort_violations_count']} interval(s) "
                f"(worst by {sim['max_temp_deviation_c']:g} °C)"
                + ("; full air-conditioning would hold it." if comfort_fixable
                   else "; even full air-conditioning cannot hold it.")
            )

        if battery_ok and comfort_ok:
            verdict = "accept"
        elif comfort_fixable is False:
            verdict = "reject"
        else:
            verdict = "re_optimize"

        return {
            "verdict": verdict,
            "reasons": reasons,
            "checks": {
                "is_thermal_feasible": comfort_ok,
                "comfort_fixable_by_hvac": comfort_fixable,
                "battery_soc_violations": sim["battery_soc_violations_count"],
                "charge_limit_breaches": len(over_charge),
                "discharge_limit_breaches": len(over_discharge),
                "simultaneous_charge_discharge": len(simultaneous),
                "max_soc_gap_vs_solver_kwh": soc_gap_kwh,
                "hvac_schedule_source": "plan" if plan_has_hvac else sim["hvac_mode"],
            },
            "simulation": sim,
        }
