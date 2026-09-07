"""
CampusGrid AI: Simulation Tool (MCP-Compliant)
Executes 2R2C continuous thermal physics equations and evaluates ASHRAE-55 comfort feasibility.
"""

import time
from typing import Dict, Any, List
from src.domain.interfaces.tool import Tool, ToolResult

class SimulationTool(Tool):
    """MCP tool executing building thermal grey-box differential equations."""

    def __init__(self, c_in: float = 50.0, r_vent: float = 2.5):
        self.c_in = c_in
        self.r_vent = r_vent

    @property
    def name(self) -> str:
        return "simulate_building_thermal_dynamics"

    @property
    def description(self) -> str:
        return "Solves continuous 2R2C thermal physics differential equations to predict indoor temperature trajectories."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "required": ["initial_temp_c", "ambient_temps", "occupant_counts", "hvac_power_kw"],
            "properties": {
                "initial_temp_c": {"type": "number", "description": "Starting indoor temperature (°C)"},
                "ambient_temps": {"type": "array", "items": {"type": "number"}},
                "occupant_counts": {"type": "array", "items": {"type": "integer"}},
                "hvac_power_kw": {"type": "array", "items": {"type": "number"}},
                "dt_hours": {"type": "number", "default": 0.5}
            }
        }

    def execute(self, **kwargs) -> ToolResult:
        start_time = time.time()
        initial_temp = float(kwargs.get("initial_temp_c", 24.0))
        ambient_temps = kwargs.get("ambient_temps", [])
        occupants = kwargs.get("occupant_counts", [])
        hvac_powers = kwargs.get("hvac_power_kw", [])
        dt_hours = float(kwargs.get("dt_hours", 0.5))

        temp_history = [initial_temp]
        violations = 0
        max_deviation = 0.0

        for t_amb, occ, q_hvac in zip(ambient_temps, occupants, hvac_powers):
            q_occ = occ * 0.10  # 100 Watts per student body
            q_transfer = (t_amb - temp_history[-1]) / self.r_vent
            delta_t = (q_transfer + q_occ - q_hvac) * (dt_hours / self.c_in)
            next_temp = round(temp_history[-1] + delta_t, 2)
            temp_history.append(next_temp)

            # Check ASHRAE-55 limits (21.0°C - 25.5°C)
            if next_temp < 21.0 or next_temp > 25.5:
                violations += 1
                dev = max(21.0 - next_temp, next_temp - 25.5)
                if dev > max_deviation:
                    max_deviation = dev

        elapsed = (time.time() - start_time) * 1000.0

        return ToolResult(
            success=True,
            data={
                "indoor_temperatures_c": temp_history[1:],
                "comfort_violation_count": violations,
                "max_temp_deviation_c": round(max_deviation, 2),
                "is_feasible": (violations == 0),
                "min_observed_c": min(temp_history[1:]) if len(temp_history) > 1 else initial_temp,
                "max_observed_c": max(temp_history[1:]) if len(temp_history) > 1 else initial_temp
            },
            execution_time_ms=elapsed
        )
