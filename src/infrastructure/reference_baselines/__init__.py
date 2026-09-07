"""
CampusGrid AI: Reference Baselines
Gold-standard baseline implementations of forecasters, thermal twin models, and MILP solvers.
These serve as architectural benchmarks and can be used for reference or mock testing.
"""

from .baseline_forecaster import BaselineDemandForecaster
from .baseline_thermal import BaselineBuildingThermalTwin, BaselineBatteryDynamicsModel
from .baseline_milp import BaselineCampusMicrogridOptimizer

__all__ = [
    "BaselineDemandForecaster",
    "BaselineBuildingThermalTwin",
    "BaselineBatteryDynamicsModel",
    "BaselineCampusMicrogridOptimizer",
]
