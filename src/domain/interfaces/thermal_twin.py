"""
CampusGrid AI: Digital Twin & Cyber-Physical Simulation Domain Interfaces
Assigned to: Member 3 (Digital Twin, Cyber-Physical Physics & Simulation)
"""

from abc import ABC, abstractmethod
from typing import List, Tuple

class BuildingThermalTwinInterface(ABC):
    """Abstract interface for 2R2C continuous building thermal network models."""

    @abstractmethod
    def simulate(
        self,
        initial_temp_c: float,
        ambient_temps: List[float],
        occupant_counts: List[int],
        hvac_power_kw: List[float],
        dt_hours: float = 0.5
    ) -> List[float]:
        """
        Simulates indoor air temperatures step-by-step using continuous differential equations.
        Returns a list of simulated indoor temperature values across intervals.
        """
        pass


class BatteryDynamicsInterface(ABC):
    """Abstract interface for BESS electrochemical state-of-charge dynamics."""

    @abstractmethod
    def simulate_soc_trajectory(
        self,
        initial_soc_kwh: float,
        charge_kw_series: List[float],
        discharge_kw_series: List[float],
        dt_hours: float = 0.5
    ) -> Tuple[List[float], int]:
        """
        Simulates battery energy level across intervals and evaluates boundary violations.
        Returns (soc_kwh_history, violation_count).
        """
        pass
