"""
Backwards compatibility shim for BuildingThermalTwin.
Delegates to src.agents.digital_twin.thermal_model.
"""

from src.agents.digital_twin.thermal_model import BuildingThermalTwin

__all__ = ["BuildingThermalTwin"]
