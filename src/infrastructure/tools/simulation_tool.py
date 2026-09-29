"""
CampusGrid AI: Simulation Tool (MCP-Compliant)
Executes 2R2C continuous thermal physics equations and evaluates ASHRAE-55 comfort feasibility.

Delegates the actual 2R2C differential equation to the injected thermal twin (the member
implementation or its reference baseline, whichever the container selected) so there is
exactly one implementation of the physics — this tool is a thin MCP-facing wrapper around it.
It depends only on the domain interface; the container supplies the twin and comfort limits.
"""

import time
from typing import Dict, Any, List, Optional
from src.domain.interfaces.tool import Tool, ToolResult
from src.domain.interfaces.thermal_twin import BuildingThermalTwinInterface
from src.shared.constants import COMFORT_TEMP_MIN_C, COMFORT_TEMP_MAX_C

# Hard physical plausibility envelope for the tool boundary. Independent of the ASHRAE-55
# comfort band (that is a target range for the *output*; these are sanity bounds on the
# *inputs* a caller — human, LLM, or a spoofed MCP client — is allowed to command).
MIN_PHYSICAL_TEMP_C = 10.0
MAX_PHYSICAL_TEMP_C = 45.0
MAX_OCCUPANTS_PER_ZONE = 5000
MAX_HVAC_POWER_KW = 1000.0
# The whole pipeline is built around a 48 half-hour-interval horizon. Anything longer is
# not a real dispatch request — it is either a bug or a compute-exhaustion attempt.
MAX_INTERVALS = 48
# Step length bounds: the pipeline uses 0.5 h; tiny or huge steps make explicit Euler meaningless.
MIN_DT_HOURS = 0.05
MAX_DT_HOURS = 1.0

class SimulationTool(Tool):
    """MCP tool executing building thermal grey-box differential equations."""

    def __init__(
        self,
        c_in: float = 50.0,
        r_vent: float = 2.5,
        thermal_twin: Optional[BuildingThermalTwinInterface] = None,
        comfort_min_c: float = COMFORT_TEMP_MIN_C,
        comfort_max_c: float = COMFORT_TEMP_MAX_C,
    ):
        self.c_in = c_in
        self.r_vent = r_vent
        if thermal_twin is None:
            # Standalone use (tests, the MCP server factory). The container always injects the twin.
            from src.agents.digital_twin.thermal_model import BuildingThermalTwin
            thermal_twin = BuildingThermalTwin(c_in=c_in, r_vent=r_vent)
        self.thermal_twin = thermal_twin
        self.comfort_min_c = comfort_min_c
        self.comfort_max_c = comfort_max_c

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

    def _validate_bounds(
        self,
        initial_temp: float,
        ambient_temps: List[float],
        occupants: List[int],
        hvac_powers: List[float],
        dt_hours: float = 0.5,
    ) -> None:
        """Rejects physically impossible parameters before any equation runs.

        Raises ValueError with a message identifying exactly which value and bound was
        violated — this is the tool-boundary rejection the MCP security audit tests against
        (e.g. commanding -15C or 5000kW must fail here, not silently produce nonsense output).
        """
        if not (MIN_PHYSICAL_TEMP_C <= initial_temp <= MAX_PHYSICAL_TEMP_C):
            raise ValueError(
                f"initial_temp_c={initial_temp} outside physical envelope "
                f"[{MIN_PHYSICAL_TEMP_C}, {MAX_PHYSICAL_TEMP_C}]"
            )
        if not (MIN_DT_HOURS <= dt_hours <= MAX_DT_HOURS):
            raise ValueError(f"dt_hours={dt_hours} outside supported step range [{MIN_DT_HOURS}, {MAX_DT_HOURS}]")
        if not (len(ambient_temps) == len(occupants) == len(hvac_powers)):
            raise ValueError(
                "ambient_temps, occupant_counts and hvac_power_kw must be equal length "
                f"(got {len(ambient_temps)}, {len(occupants)}, {len(hvac_powers)})"
            )
        if len(ambient_temps) > MAX_INTERVALS:
            raise ValueError(
                f"{len(ambient_temps)} intervals requested, exceeds the {MAX_INTERVALS}-interval "
                "horizon this pipeline is designed for"
            )
        for t_amb in ambient_temps:
            if not (MIN_PHYSICAL_TEMP_C <= t_amb <= MAX_PHYSICAL_TEMP_C):
                raise ValueError(
                    f"ambient temperature {t_amb} outside physical envelope "
                    f"[{MIN_PHYSICAL_TEMP_C}, {MAX_PHYSICAL_TEMP_C}]"
                )
        for occ in occupants:
            if not (0 <= occ <= MAX_OCCUPANTS_PER_ZONE):
                raise ValueError(
                    f"occupant_count {occ} outside plausible zone capacity [0, {MAX_OCCUPANTS_PER_ZONE}]"
                )
        for q_hvac in hvac_powers:
            if not (0 <= q_hvac <= MAX_HVAC_POWER_KW):
                raise ValueError(
                    f"hvac_power_kw {q_hvac} outside rated plant capacity [0, {MAX_HVAC_POWER_KW}]"
                )

    def execute(self, **kwargs) -> ToolResult:
        start_time = time.time()

        # Type coercion is part of the boundary, not a pre-condition for it: a caller
        # (human, LLM, or a spoofed MCP client) sending a non-numeric value here must
        # get a graceful rejection, not an unhandled exception that crashes the caller.
        try:
            initial_temp = float(kwargs.get("initial_temp_c", 24.0))
            ambient_temps = [float(t) for t in kwargs.get("ambient_temps", [])]
            occupants = [int(o) for o in kwargs.get("occupant_counts", [])]
            hvac_powers = [float(p) for p in kwargs.get("hvac_power_kw", [])]
            dt_hours = float(kwargs.get("dt_hours", 0.5))
            self._validate_bounds(initial_temp, ambient_temps, occupants, hvac_powers, dt_hours)
        except (TypeError, ValueError) as exc:
            return ToolResult(
                success=False,
                data=None,
                error=str(exc),
                execution_time_ms=(time.time() - start_time) * 1000.0,
            )

        indoor_temps = self.thermal_twin.simulate(
            initial_temp_c=initial_temp,
            ambient_temps=ambient_temps,
            occupant_counts=occupants,
            hvac_power_kw=hvac_powers,
            dt_hours=dt_hours,
        )

        comfort_min = self.comfort_min_c
        comfort_max = self.comfort_max_c
        violations = 0
        max_deviation = 0.0
        for temp in indoor_temps:
            if temp < comfort_min or temp > comfort_max:
                violations += 1
                deviation = max(comfort_min - temp, temp - comfort_max)
                max_deviation = max(max_deviation, deviation)

        elapsed = (time.time() - start_time) * 1000.0

        return ToolResult(
            success=True,
            data={
                "indoor_temperatures_c": indoor_temps,
                "comfort_violation_count": violations,
                "max_temp_deviation_c": round(max_deviation, 2),
                "is_feasible": (violations == 0),
                "min_observed_c": min(indoor_temps) if indoor_temps else initial_temp,
                "max_observed_c": max(indoor_temps) if indoor_temps else initial_temp
            },
            execution_time_ms=elapsed
        )
