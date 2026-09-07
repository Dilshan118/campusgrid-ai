"""
CampusGrid AI: Reference Baseline Thermal & Battery Models
2R2C continuous thermal model and battery degradation/SOC model.
Preserved as reference benchmarks for Member 3.
"""

from typing import List, Tuple
from src.domain.interfaces.thermal_twin import BuildingThermalTwinInterface, BatteryDynamicsInterface

class BaselineBuildingThermalTwin(BuildingThermalTwinInterface):
    """Continuous 2-Resistance 2-Capacitance thermal network simulator."""

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
        """Runs the continuous thermal differential equation across time intervals."""
        temp_history = [initial_temp_c]
        for t_amb, occ, q_hvac in zip(ambient_temps, occupant_counts, hvac_power_kw):
            q_occ = occ * 0.10  # 100 Watts per student
            q_transfer = (t_amb - temp_history[-1]) / self.r_vent
            delta_t = (q_transfer + q_occ - q_hvac) * (dt_hours / self.c_in)
            next_temp = round(temp_history[-1] + delta_t, 2)
            temp_history.append(next_temp)
        return temp_history[1:]


class BaselineBatteryDynamicsModel(BatteryDynamicsInterface):
    """Simulates BESS charge/discharge transitions, efficiency losses, and SOC."""

    def __init__(
        self,
        capacity_kwh: float = 500.0,
        max_power_kw: float = 100.0,
        min_soc_pct: float = 0.20,
        max_soc_pct: float = 0.90,
        round_trip_eff: float = 0.92
    ):
        self.capacity_kwh = capacity_kwh
        self.max_power_kw = max_power_kw
        self.min_soc_pct = min_soc_pct
        self.max_soc_pct = max_soc_pct
        self.round_trip_eff = round_trip_eff
        self.one_way_eff = round_trip_eff ** 0.5

    def simulate_soc_trajectory(
        self,
        initial_soc_kwh: float,
        charge_kw_series: List[float],
        discharge_kw_series: List[float],
        dt_hours: float = 0.5
    ) -> Tuple[List[float], int]:
        """
        Simulates battery energy level across intervals.
        Returns: (soc_kwh_history, violation_count)
        """
        soc_history = []
        current_soc = initial_soc_kwh
        violations = 0

        min_kwh = self.capacity_kwh * self.min_soc_pct
        max_kwh = self.capacity_kwh * self.max_soc_pct

        for c_kw, d_kw in zip(charge_kw_series, discharge_kw_series):
            energy_in = c_kw * self.one_way_eff * dt_hours
            energy_out = (d_kw / self.one_way_eff) * dt_hours

            current_soc += energy_in - energy_out
            current_soc = round(current_soc, 2)
            soc_history.append(current_soc)

            if current_soc < min_kwh or current_soc > max_kwh:
                violations += 1

        return soc_history, violations
