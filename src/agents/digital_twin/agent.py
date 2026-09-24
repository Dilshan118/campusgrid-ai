"""
CampusGrid AI: Agent 2 — Digital Twin Simulation (Physics · Simulation)
Executes 2R2C building thermal physics, evaluates ASHRAE-55 comfort, and validates battery SOC envelopes.
Runs what-if environmental and crowd perturbation simulations.
"""

from typing import Dict, Any, List, Optional
from src.agents.base.agent import BaseAgent
from src.agents.digital_twin.thermal_model import BuildingThermalTwin
from src.domain.interfaces.tool import Tool
from src.domain.interfaces.thermal_twin import BuildingThermalTwinInterface, BatteryDynamicsInterface
from src.agents.digital_twin.battery_dynamics import BatteryDynamicsModel
from src.config.settings import get_settings

class DigitalTwinAgent(BaseAgent):
    """Agent 2: Cyber-physical simulator validating feasibility and what-if scenarios."""

    def __init__(
        self,
        simulation_tool: Optional[Tool] = None,
        thermal_twin: Optional[BuildingThermalTwinInterface] = None,
        battery_dynamics: Optional[BatteryDynamicsInterface] = None
    ):
        super().__init__(
            name="Agent 2: Digital Twin Simulation",
            description="Solves 2R2C grey-box differential equations and checks physical feasibility."
        )
        self.simulation_tool = simulation_tool
        self.thermal_twin = thermal_twin or BuildingThermalTwin()
        self.battery_dynamics = battery_dynamics or BatteryDynamicsModel()

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

        # If HVAC proposal not supplied, create standard baseline cooling curve
        if not hvac_proposal:
            hvac_proposal = [
                35.0 if (8 <= (i // 2) <= 17) else 5.0
                for i in range(len(perturbed_ambients))
            ]
        hvac_proposal = [round(p * solar_scaling_factor, 2) for p in hvac_proposal]

        # Run 2R2C continuous thermal model
        indoor_temps = self.thermal_twin.simulate(
            initial_temp_c=initial_temp,
            ambient_temps=perturbed_ambients,
            occupant_counts=perturbed_occupants,
            hvac_power_kw=hvac_proposal
        )

        comfort_min = get_settings().physics.comfort_min_temp_c
        comfort_max = get_settings().physics.comfort_max_temp_c
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
        battery_capacity_kwh = get_settings().physics.battery_capacity_kwh
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
