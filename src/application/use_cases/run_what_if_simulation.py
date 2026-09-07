"""
CampusGrid AI: Digital Twin What-If Simulation Use Case
Evaluates building thermal feasibility under heatwaves and crowd surges.
"""

from typing import Dict, Any, List
from src.agents.digital_twin.agent import DigitalTwinAgent

class RunWhatIfSimulationUseCase:
    """Executes cyber-physical what-if perturbation scenarios."""

    def __init__(self, digital_twin_agent: DigitalTwinAgent):
        self.twin = digital_twin_agent

    def execute(
        self,
        initial_temp_c: float = 24.0,
        temp_delta_c: float = 0.0,
        occupancy_multiplier: float = 1.0,
        ambient_temps: List[float] = None,
        occupancies: List[int] = None,
        hvac_powers: List[float] = None
    ) -> Dict[str, Any]:
        ambients = ambient_temps or [
            26.2, 26.0, 25.8, 25.7, 25.5, 25.4, 25.3, 25.2, 25.1, 25.2, 25.4, 25.8,
            26.5, 27.2, 28.0, 28.8, 29.5, 30.2, 30.8, 31.4, 32.0, 32.5, 33.0, 33.4,
            33.8, 34.0, 33.9, 33.5, 32.8, 32.0, 31.2, 30.5, 29.8, 29.2, 28.8, 28.4,
            28.1, 27.8, 27.5, 27.2, 27.0, 26.8, 26.6, 26.5, 26.4, 26.3, 26.2, 26.1
        ]
        occs = occupancies or [20, 15, 10, 10, 5, 5, 5, 5, 10, 15, 30, 50, 120, 250, 500, 850, 1200, 1400, 1500, 1550, 1600, 1600, 1620, 1600, 1580, 1500, 1450, 1400, 1350, 1200, 1000, 800, 600, 400, 300, 200, 150, 100, 80, 60, 50, 40, 30, 25, 20, 20, 20, 20]

        payload = {
            "initial_temp_c": initial_temp_c,
            "ambient_temperatures_c": ambients,
            "occupancy_counts": occs,
            "hvac_power_kw": hvac_powers or [],
            "perturb_temp_delta_c": temp_delta_c,
            "perturb_occ_multiplier": occupancy_multiplier
        }

        res = self.twin.execute(payload)
        return {"success": res.success, "data": res.data, "error": res.error}
