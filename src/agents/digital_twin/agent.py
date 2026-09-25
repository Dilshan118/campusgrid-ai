"""
CampusGrid AI: Agent 2 — Digital Twin Simulation (Physics · Simulation)
Executes 2R2C building thermal physics, evaluates ASHRAE-55 comfort, and validates battery SOC envelopes.
Runs what-if environmental and crowd perturbation simulations.
"""

import math
from typing import Dict, Any, List, Optional
from src.agents.base.agent import BaseAgent
from src.agents.digital_twin.thermal_model import BuildingThermalTwin
from src.domain.interfaces.tool import Tool
from src.domain.interfaces.thermal_twin import BuildingThermalTwinInterface, BatteryDynamicsInterface
from src.agents.digital_twin.battery_dynamics import BatteryDynamicsModel
from src.shared.constants import COMFORT_TEMP_MIN_C, COMFORT_TEMP_MAX_C, BATTERY_CAPACITY_DEFAULT_KWH

# Rated cooling one zone can draw when a setpoint is controlled (kW thermal). Settings override it.
DEFAULT_HVAC_MAX_COOLING_KW = 35.0
_THERMOSTAT_BISECTION_STEPS = 20

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
        # Fraction of nominal HVAC/chiller power actually available. A solar dropout
        # scenario derates this below 1.0 to represent lost rooftop-PV cooling capacity.
        solar_scaling_factor = float(input_data.get("perturb_solar_scaling_factor", 1.0))

        perturbed_ambients = [round(t + temp_delta, 2) for t in ambient_temps]
        perturbed_occupants = [int(o * occ_multiplier) for o in occupants]
        setpoint = input_data.get("target_setpoint_c")

        if hvac_proposal:
            hvac_mode = "supplied"
            hvac_proposal = [round(p * solar_scaling_factor, 2) for p in hvac_proposal]
        elif setpoint is not None:
            # Thermostat: cool towards the requested setpoint, within the (derated) plant capacity.
            hvac_mode = "thermostat"
            hvac_proposal = self._thermostat_schedule(
                initial_temp, perturbed_ambients, perturbed_occupants, float(setpoint),
                self.hvac_max_cooling_kw * solar_scaling_factor,
            )
        else:
            # No plan and no setpoint: standard office-hours cooling curve.
            hvac_mode = "default_schedule"
            hvac_proposal = [
                round((35.0 if (8 <= (i // 2) <= 17) else 5.0) * solar_scaling_factor, 2)
                for i in range(len(perturbed_ambients))
            ]

        # Run 2R2C continuous thermal model
        indoor_temps = self.thermal_twin.simulate(
            initial_temp_c=initial_temp,
            ambient_temps=perturbed_ambients,
            occupant_counts=perturbed_occupants,
            hvac_power_kw=hvac_proposal
        )

        comfort_min = float(input_data.get("comfort_min_c", self.comfort_min_c))
        comfort_max = float(input_data.get("comfort_max_c", self.comfort_max_c))
        comfort_violations = 0
        max_deviation_c = 0.0
        for t in indoor_temps:
            if t < comfort_min or t > comfort_max:
                comfort_violations += 1
                max_deviation_c = max(max_deviation_c, comfort_min - t, t - comfort_max)
        is_feasible = (comfort_violations == 0)

        # Battery safety check. Callers that only care about thermal feasibility (e.g.
        # the existing what-if API route) do not supply a charge/discharge plan — default
        # to an idle battery (no activity) so the SOC trajectory is still returned, flat
        # and violation-free, rather than silently skipped.
        battery_capacity_kwh = self.battery_capacity_kwh
        battery_initial_soc_kwh = float(
            input_data.get("battery_initial_soc_kwh", battery_capacity_kwh * 0.5)
        )
        battery_charge_kw = input_data.get("battery_charge_kw", [0.0] * len(perturbed_ambients))
        battery_discharge_kw = input_data.get("battery_discharge_kw", [0.0] * len(perturbed_ambients))

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
            }
        }

    def _thermostat_schedule(
        self,
        initial_temp: float,
        ambients: List[float],
        occupants: List[int],
        setpoint: float,
        max_cooling_kw: float,
    ) -> List[float]:
        """Per interval, the least cooling that keeps the room at or below the setpoint.

        Found by bisection on the injected twin (member or baseline), re-simulating the whole
        prefix each time so any hidden state (e.g. the 2R2C wall temperature) carries over.
        Where even full capacity cannot hold the setpoint, the plant runs flat out.
        """
        schedule: List[float] = []
        for t in range(len(ambients)):
            def end_temp(q_kw: float) -> float:
                return self.thermal_twin.simulate(
                    initial_temp_c=initial_temp,
                    ambient_temps=ambients[: t + 1],
                    occupant_counts=occupants[: t + 1],
                    hvac_power_kw=schedule + [q_kw],
                )[-1]

            if end_temp(0.0) <= setpoint:
                schedule.append(0.0)
                continue
            if end_temp(max_cooling_kw) > setpoint:
                schedule.append(round(max_cooling_kw, 2))
                continue
            low, high = 0.0, max_cooling_kw
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
    ) -> Dict[str, Dict[str, Any]]:
        """Runs the three required what-if scenarios against one baseline forecast:
        a heatwave, a crowd surge, and a solar dropout. Each result reports whether the
        building stays inside the comfort band and the battery stays inside its SOC
        band, and if not, by how much either misses."""
        baseline = {
            "initial_temp_c": initial_temp_c,
            "ambient_temperatures_c": ambient_temperatures_c,
            "occupancy_counts": occupancy_counts,
            "hvac_power_kw": hvac_power_kw or [],
        }
        if battery_initial_soc_kwh is not None:
            baseline["battery_initial_soc_kwh"] = battery_initial_soc_kwh
        if battery_charge_kw is not None:
            baseline["battery_charge_kw"] = battery_charge_kw
        if battery_discharge_kw is not None:
            baseline["battery_discharge_kw"] = battery_discharge_kw

        scenarios = {
            "heatwave": {**baseline, "perturb_temp_delta_c": 4.0},
            "crowd_surge": {**baseline, "perturb_occ_multiplier": 2.0},
            "solar_dropout": {**baseline, "perturb_solar_scaling_factor": 0.5},
        }

        return {
            scenario_name: self._run(scenario_input)
            for scenario_name, scenario_input in scenarios.items()
        }
