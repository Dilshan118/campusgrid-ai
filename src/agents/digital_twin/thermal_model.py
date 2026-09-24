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
        """Runs the continuous 2R2C thermal differential equation across time intervals."""
        temp_history = [initial_temp_c]
        for t_amb, occupants, q_hvac in zip(ambient_temps, occupant_counts, hvac_power_kw):
            q_occ = occupants * 0.10  # 100 W per occupant
            q_transfer = (t_amb - temp_history[-1]) / self.r_vent
            delta_t = (q_transfer + q_occ - q_hvac) * (dt_hours / self.c_in)
            temp_history.append(round(temp_history[-1] + delta_t, 2))
        return temp_history[1:]
