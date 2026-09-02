"""
Member 3 Workstream: 2R2C Grey-Box Building Thermal Model
Implements continuous differential equations simulating room temperatures
based on building envelope heat transfer, ambient weather, and occupant heat.
"""

from typing import List

class BuildingThermalTwin:
    """
    Simulates indoor temperature dynamics using 2-Resistance 2-Capacitance physics.
    
    Equations:
    dT_in / dt = (1 / (R_in * C_in)) * (T_wall - T_in) + (1 / (R_vent * C_in)) * (T_amb - T_in)
                 + (Q_occupants + Q_solar - Q_hvac) / C_in
    
    Occupant heat = 100 Watts (0.10 kW) per student body.
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
        Runs the thermal simulation across the time horizon.
        Returns the indoor temperature series.
        """
        temp_history = [initial_temp_c]
        for t_amb, occ, q_hvac in zip(ambient_temps, occupant_counts, hvac_power_kw):
            q_occ = occ * 0.10  # 100W per occupant
            q_transfer = (t_amb - temp_history[-1]) / self.r_vent
            delta_t = (q_transfer + q_occ - q_hvac) * (dt_hours / self.c_in)
            temp_history.append(temp_history[-1] + delta_t)
        return temp_history[1:]
