"""
CampusGrid AI: Agent 1 — 24-Hour Campus Demand & Solar Forecaster
Module Owner: Member 2 (Telemetry, Data Engineering & Machine Learning)

RESPONSIBILITIES:
1. Ingest historical meter intervals, ambient temperature series, and scheduled classroom occupancy.
2. Predict 24-hour / 48 half-hour baseline electrical demand (kW) and rooftop solar PV generation (kW).
3. Compute 95% confidence intervals (lower_bound_kw and upper_bound_kw).
4. Detect demand anomalies (e.g. unexpected spikes exceeding safety thresholds).
5. (Optional / Advanced): Integrate trained LightGBM/XGBoost model from `src/pipelines/periodic_retraining/`.
"""

from typing import List, Dict, Any
from src.domain.entities.telemetry import TelemetryInterval, PowerForecast
from src.domain.interfaces.forecaster import DemandForecasterInterface

class DemandForecaster(DemandForecasterInterface):
    """
    Predictive model for campus electricity demand and solar generation.
    Assigned to: Member 2
    """

    def __init__(self, model_version: str = "v4.2-member2-forecaster"):
        self.model_version = model_version

    def predict(
        self,
        historical_intervals: List[TelemetryInterval],
        temperature_series: List[float],
        occupancy_counts: List[int]
    ) -> PowerForecast:
        """
        Calculates 48-period (half-hourly) day-ahead load and solar forecast.

        # =========================================================================
        # TODO (Member 2: Telemetry & Forecasting):
        # Implement your forecasting algorithm here!
        #
        # STEPS TO IMPLEMENT:
        # 1. Loop through `historical_intervals` (each representing a 30-min slot).
        # 2. Extract base load, solar generation, ambient temperature, and occupancy.
        # 3. Apply your ML model (or physics-informed statistical formulas):
        #    - Cooling sensitivity: Add extra kW if temperature exceeds 28°C.
        #    - Occupancy factor: Add equipment kW per student in the room.
        # 4. Calculate 95% confidence intervals (+/- 6% bounds).
        # 5. Flag any anomaly intervals where demand exceeds threshold (e.g., > 850 kW).
        # 6. Return a populated `PowerForecast` entity.
        #
        # NOTE: A fully working baseline reference is available for guidance in:
        # `src/infrastructure/reference_baselines/baseline_forecaster.py`
        # =========================================================================
        """
        raise NotImplementedError(
            "Member 2: Please implement DemandForecaster.predict() in src/agents/telemetry/forecaster.py. "
            "See TEAM_GUIDES/MEMBER_2_TELEMETRY_AND_PRIVACY_GUIDE.md for exact instructions and Claude Code prompts."
        )
