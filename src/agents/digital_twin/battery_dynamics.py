"""
CampusGrid AI: Agent 2 — Battery Electrochemical Dynamics & Degradation Model
Module Owner: Member 3 (Digital Twin, Cyber-Physical Physics & Simulation)

RESPONSIBILITIES:
1. Model BESS (Battery Energy Storage System) energy level transitions.
2. Factor in round-trip efficiency losses (e.g. 92% -> sqrt(0.92) one-way efficiency).
3. Track and validate State-of-Charge (SOC) bounds (20% to 90% of nominal capacity).
4. Count and log SOC envelope violations for red-teaming and safety assurance.
"""

from typing import List, Tuple
from src.domain.interfaces.thermal_twin import BatteryDynamicsInterface

class BatteryDynamicsModel(BatteryDynamicsInterface):
    """
    Simulates BESS charge/discharge transitions, efficiency losses, and SOC.
    Assigned to: Member 3
    """

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
        current_soc = initial_soc_kwh
        soc_history: List[float] = []
        violations = 0

        min_kwh = self.capacity_kwh * self.min_soc_pct
        max_kwh = self.capacity_kwh * self.max_soc_pct

        for charge_kw, discharge_kw in zip(charge_kw_series, discharge_kw_series):
            energy_in = charge_kw * self.one_way_eff * dt_hours
            energy_out = (discharge_kw / self.one_way_eff) * dt_hours
            current_soc = round(current_soc + energy_in - energy_out, 2)
            soc_history.append(current_soc)

            if current_soc < min_kwh or current_soc > max_kwh:
                violations += 1

        return soc_history, violations
