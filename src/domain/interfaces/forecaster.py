"""
CampusGrid AI: Demand and Solar Forecaster Domain Interface
Assigned to: Member 2 (Telemetry & Machine Learning)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from src.domain.entities.telemetry import TelemetryInterval, PowerForecast

class DemandForecasterInterface(ABC):
    """Abstract interface for day-ahead campus demand and solar PV generation forecasting."""

    @abstractmethod
    def predict(
        self,
        historical_intervals: List[TelemetryInterval],
        temperature_series: List[float],
        occupancy_counts: List[int]
    ) -> PowerForecast:
        """
        Projects 48 half-hour intervals of campus load and solar generation.
        Returns a PowerForecast containing baseline predictions and confidence intervals.
        """
        pass


class ForecasterTrainerInterface(ABC):
    """Abstract interface for offline ML regression model training pipelines."""

    @abstractmethod
    def train(self, output_model_path: str = "src/agents/telemetry/model.joblib") -> Dict[str, Any]:
        """Trains an ML model on historical campus meter and occupancy logs."""
        pass
