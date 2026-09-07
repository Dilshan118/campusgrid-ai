"""
CampusGrid AI: Agent 2 — 2R2C Continuous Building Thermal Grey-Box Model
Module Owner: Member 3 (Digital Twin, Cyber-Physical Physics & Simulation)

RESPONSIBILITIES:
1. Model classroom thermal dynamics via 2-Resistance 2-Capacitance (2R2C) differential network:
   dT_in / dt = (1 / (R_in * C_in)) * (T_wall - T_in)
              + (1 / (R_vent * C_in)) * (T_amb - T_in)
              + (Q_occupants + Q_solar - Q_hvac) / C_in
2. Simulate indoor air temperature step-by-step across 30-minute intervals.
3. Validate ASHRAE-55 human thermal comfort envelope (21.0°C <= T_in <= 25.5°C).
4. Evaluate thermal perturbations (e.g. +3°C heatwave or 2x crowd surge).
"""

from typing import List
from src.domain.interfaces.thermal_twin import BuildingThermalTwinInterface

class BuildingThermalTwin(BuildingThermalTwinInterface):
    """
    Continuous 2-Resistance 2-Capacitance thermal network simulator.
    Assigned to: Member 3
    """

    def __init__(self, c_in: float = 50.0, r_vent: float = 2.5):
        self.c_in = c_in        # Thermal capacitance (kWh / °C)
        self.r_vent = r_vent    # Thermal resistance (°C / kW)

    def simulate(
        self,
        initial_temp_c: float,
        ambient_temps: List[float],
        occupant_counts: List[int],
        hvac_power_kw: List[float],
        dt_hours: float = 0.5
    ) -> List[float]:
        """
        Runs the continuous thermal differential equation across time intervals.

        # =========================================================================
        # TODO (Member 3: 2R2C Grey-Box Physics):
        # Implement your thermal physics simulation here!
        #
        # STEPS TO IMPLEMENT:
        # 1. Start with `temp_history = [initial_temp_c]`.
        # 2. For each time step (zip ambient_temps, occupant_counts, hvac_power_kw):
        #    a. Calculate occupant heat gain: Q_occ = occupants * 0.10 kW (100W/person).
        #    b. Calculate envelope heat transfer: Q_transfer = (T_amb - current_temp) / r_vent.
        #    c. Compute temperature change delta_t:
        #       delta_t = (Q_transfer + Q_occ - Q_hvac) * (dt_hours / c_in).
        #    d. Update indoor temp: next_temp = current_temp + delta_t.
        # 3. Return the simulated indoor temperatures series (excluding initial temp).
        #
        # NOTE: A fully working baseline reference is available for guidance in:
        # `src/infrastructure/reference_baselines/baseline_thermal.py`
        # =========================================================================
        """
        raise NotImplementedError(
            "Member 3: Please implement BuildingThermalTwin.simulate() in src/agents/digital_twin/thermal_model.py. "
            "See TEAM_GUIDES/MEMBER_3_DIGITAL_TWIN_AND_PHYSICS_GUIDE.md for exact instructions and Claude Code prompts."
        )
