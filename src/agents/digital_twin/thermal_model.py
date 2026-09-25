"""
CampusGrid AI: Agent 2 — 2R2C Continuous Building Thermal Grey-Box Model
Module Owner: Member 3 (Digital Twin, Cyber-Physical Physics & Simulation)

RESPONSIBILITIES:
1. Model classroom thermal dynamics via the 2-Resistance 2-Capacitance (2R2C) network of
   SRS section 6.1 — two thermal masses (indoor air C_in, building envelope C_wall):
   dT_in / dt   = (1 / (R_in * C_in)) * (T_wall - T_in)
                + (1 / (R_vent * C_in)) * (T_amb - T_in)
                + (Q_occupants - Q_hvac) / C_in
   dT_wall / dt = (1 / (R_in * C_wall)) * (T_in - T_wall)
                + (1 / (R_out * C_wall)) * (T_amb - T_wall)
   (Q_solar from the SRS is not modelled: no irradiance input exists in the pipeline yet.)
2. Simulate indoor air temperature step-by-step across 30-minute intervals (explicit Euler).
3. Validate ASHRAE-55 human thermal comfort envelope (21.0°C <= T_in <= 25.5°C).
4. Evaluate thermal perturbations (e.g. +3°C heatwave or 2x crowd surge).

c_in and r_vent are the constants fitted in thermal_calibration.py. The wall constants are
documented, uncalibrated defaults (see src/config/settings.py) until measured data exists.
"""

from typing import List, Optional
from src.domain.interfaces.thermal_twin import BuildingThermalTwinInterface
from src.shared.constants import HEAT_PER_OCCUPANT_KW

class BuildingThermalTwin(BuildingThermalTwinInterface):
    """
    Continuous 2-Resistance 2-Capacitance thermal network simulator.
    Assigned to: Member 3
    """

    def __init__(
        self,
        c_in: float = 50.0,
        r_vent: float = 2.5,
        c_wall: float = 200.0,
        r_in: float = 2.0,
        r_out: float = 6.0,
    ):
        self.c_in = c_in        # Indoor air thermal capacitance (kWh / °C)
        self.r_vent = r_vent    # Ventilation resistance, indoor <-> outdoor air (°C / kW)
        self.c_wall = c_wall    # Envelope (wall) thermal capacitance (kWh / °C)
        self.r_in = r_in        # Wall surface <-> indoor air resistance (°C / kW)
        self.r_out = r_out      # Wall <-> outdoor air resistance (°C / kW)

    def simulate(
        self,
        initial_temp_c: float,
        ambient_temps: List[float],
        occupant_counts: List[int],
        hvac_power_kw: List[float],
        dt_hours: float = 0.5,
        initial_wall_temp_c: Optional[float] = None,
    ) -> List[float]:
        """Runs the 2R2C equations across time intervals; returns indoor air temperatures.

        The wall starts at the indoor temperature unless `initial_wall_temp_c` is given
        (a building that has been conditioned overnight).
        """
        t_in = initial_temp_c
        t_wall = initial_temp_c if initial_wall_temp_c is None else initial_wall_temp_c
        indoor_history: List[float] = []
        for t_amb, occupants, q_hvac in zip(ambient_temps, occupant_counts, hvac_power_kw):
            q_occ = occupants * HEAT_PER_OCCUPANT_KW  # 100 W per occupant
            q_wall_to_air = (t_wall - t_in) / self.r_in
            q_vent = (t_amb - t_in) / self.r_vent
            q_amb_to_wall = (t_amb - t_wall) / self.r_out

            t_in = round(t_in + (q_wall_to_air + q_vent + q_occ - q_hvac) * (dt_hours / self.c_in), 2)
            t_wall = t_wall + (q_amb_to_wall - q_wall_to_air) * (dt_hours / self.c_wall)
            indoor_history.append(t_in)
        return indoor_history
