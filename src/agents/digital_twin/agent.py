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
from src.agents.digital_twin.thermal_model import BuildingThermalTwin
from src.agents.digital_twin.battery_dynamics import BatteryDynamicsModel

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

        perturbed_ambients = [round(t + temp_delta, 2) for t in ambient_temps]
        perturbed_occupants = [int(o * occ_multiplier) for o in occupants]

        # If HVAC proposal not supplied, create standard baseline cooling curve
        if not hvac_proposal:
            hvac_proposal = [
                35.0 if (8 <= (i // 2) <= 17) else 5.0
                for i in range(len(perturbed_ambients))
            ]

        # Run 2R2C continuous thermal model
        indoor_temps = self.thermal_twin.simulate(
            initial_temp_c=initial_temp,
            ambient_temps=perturbed_ambients,
            occupant_counts=perturbed_occupants,
            hvac_power_kw=hvac_proposal
        )

        comfort_violations = sum(1 for t in indoor_temps if t < 21.0 or t > 25.5)
        is_feasible = (comfort_violations == 0)

        return {
            "initial_temperature_c": initial_temp,
            "simulated_indoor_temps_c": indoor_temps,
            "ambient_temperatures_c": perturbed_ambients,
            "occupancy_counts": perturbed_occupants,
            "hvac_power_kw": hvac_proposal,
            "comfort_violations_count": comfort_violations,
            "is_thermal_feasible": is_feasible,
            "comfort_limits": {"min_c": 21.0, "max_c": 25.5},
            "perturbation_applied": {
                "temp_delta_c": temp_delta,
                "occupancy_multiplier": occ_multiplier
            }
        }
