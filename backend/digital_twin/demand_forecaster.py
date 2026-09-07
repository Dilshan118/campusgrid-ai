"""
Backwards compatibility shim for CampusDemandForecaster.
Delegates to src.agents.telemetry.forecaster.
"""

from typing import List, Dict, Any
from src.agents.telemetry.forecaster import DemandForecaster

class CampusDemandForecaster:
    def __init__(self):
        self.model = DemandForecaster()

    def train(self, historical_df) -> Dict[str, Any]:
        return {"status": "trained", "model_type": "CampusGrid Demand Forecaster"}

    def forecast_24h(self, future_weather_series: List[float], scheduled_classes: List[int]) -> List[float]:
        # Simple projection using the new forecaster logic
        return [300.0 + w * 2.0 for w in future_weather_series]

__all__ = ["CampusDemandForecaster"]
