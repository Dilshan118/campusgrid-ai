"""
CampusGrid AI: Agent 1 — 24-Hour Campus Demand & Solar Forecaster
Module Owner: Member 2 (Telemetry, Data Engineering & Machine Learning)

RESPONSIBILITIES:
1. Ingest historical meter intervals, ambient temperature series, and scheduled classroom occupancy.
2. Predict 24-hour / 48 half-hour baseline electrical demand (kW) and rooftop solar PV generation (kW).
3. Compute 95% confidence intervals (lower_bound_kw and upper_bound_kw).
4. Detect demand anomalies (e.g. unexpected spikes exceeding safety thresholds).

Two prediction paths:
- If `src/pipelines/periodic_retraining/train_forecaster.py` has been run, a trained
  model artifact exists (see `model_utils.load_model_artifact`) and is used directly.
- Otherwise, a physics-informed statistical formula is used so the agent never raises
  NotImplementedError and the system keeps working before training has happened.
"""

from typing import List, Dict, Any, Optional
from statistics import pstdev

from src.domain.entities.telemetry import TelemetryInterval, PowerForecast
from src.domain.interfaces.forecaster import DemandForecasterInterface
from src.agents.telemetry.model_utils import (
    build_feature_vector,
    linear_predict,
    load_model_artifact,
)

DEFAULT_MODEL_PATH = "src/agents/telemetry/model_forecaster.json"

# Absolute safety ceiling: any predicted interval above this is always flagged,
# regardless of how the rest of the day looks (mirrors the 100 kW site rate limit
# headroom used elsewhere in the system).
ANOMALY_ABSOLUTE_FLOOR_KW = 850.0


class DemandForecaster(DemandForecasterInterface):
    """
    Predictive model for campus electricity demand and solar generation.
    Assigned to: Member 2
    """

    def __init__(self, model_version: str = "v4.2-member2-forecaster", model_path: str = DEFAULT_MODEL_PATH):
        self.model_version = model_version
        self.model_path = model_path
        self._model_artifact: Optional[Dict[str, Any]] = load_model_artifact(model_path)

    def predict(
        self,
        historical_intervals: List[TelemetryInterval],
        temperature_series: List[float],
        occupancy_counts: List[int]
    ) -> PowerForecast:
        """Calculates 48-period (half-hourly) day-ahead load and solar forecast."""
        n = len(historical_intervals)
        slots: List[str] = []
        demands: List[float] = []
        solars: List[float] = []
        residuals: List[float] = []

        for idx, item in enumerate(historical_intervals):
            temp = temperature_series[idx] if idx < len(temperature_series) else item.outdoor_temp_c
            occ = occupancy_counts[idx] if idx < len(occupancy_counts) else item.zone_occupancy_count

            pred_demand = self._predict_demand(item.time_slot, temp, occ, fallback_base_kw=item.base_load_kw)
            pred_solar = self._predict_solar(item.solar_gen_kw, temp)

            slots.append(item.time_slot)
            demands.append(round(pred_demand, 1))
            solars.append(round(pred_solar, 1))

        residual_std = self._residual_std()
        mean_demand = sum(demands) / n if n else 0.0
        pop_std = pstdev(demands) if n > 1 else 0.0

        lowers: List[float] = []
        uppers: List[float] = []
        anomalies: List[int] = []

        for idx, pred_demand in enumerate(demands):
            lower, upper = self._confidence_bounds(pred_demand, residual_std)
            lowers.append(round(lower, 1))
            uppers.append(round(upper, 1))

            is_relative_spike = pop_std > 0 and pred_demand > mean_demand + 2.0 * pop_std
            is_absolute_spike = pred_demand > ANOMALY_ABSOLUTE_FLOOR_KW
            if is_relative_spike or is_absolute_spike:
                anomalies.append(idx)

        model_version = (
            f"{self.model_version}-{self._model_artifact.get('model_type', 'unknown')}"
            if self._model_artifact
            else f"{self.model_version}-statistical-fallback"
        )

        return PowerForecast(
            time_slots=slots,
            forecast_demand_kw=demands,
            forecast_solar_kw=solars,
            lower_bound_kw=lowers,
            upper_bound_kw=uppers,
            anomaly_indices=anomalies,
            model_version=model_version
        )

    def _predict_demand(self, time_slot: str, temp: float, occ: float, fallback_base_kw: float) -> float:
        if self._model_artifact and self._model_artifact.get("model_type") == "linear_regression":
            feature_vector = build_feature_vector(time_slot, temp, occ)
            return max(
                0.0,
                linear_predict(
                    self._model_artifact["weights"],
                    self._model_artifact["bias"],
                    self._model_artifact["means"],
                    self._model_artifact["stds"],
                    feature_vector,
                )
            )
        return self._statistical_demand(temp, occ, fallback_base_kw)

    @staticmethod
    def _statistical_demand(temp: float, occ: float, fallback_base_kw: float) -> float:
        """
        Physics-informed fallback used until a model has been trained.

        - Cooling load kicks in above 27 C, at 12 kW per degree (compressor duty rises
          roughly linearly with the indoor/outdoor delta once ambient exceeds comfort).
        - Each occupant adds ~0.08 kW of equipment/device draw (laptops, lighting, fans).
        """
        cooling_delta = max(0.0, temp - 27.0) * 12.0
        occupancy_delta = occ * 0.08
        return max(0.0, fallback_base_kw + cooling_delta + occupancy_delta)

    @staticmethod
    def _predict_solar(historical_solar_kw: float, temp: float) -> float:
        """
        Scales the seed day's solar generation by a clear-sky proxy: hotter tropical
        afternoons in this climate are typically clearer (less monsoon cloud cover),
        so generation is nudged up slightly; the factor is bounded to stay physically
        plausible even for extreme inputs.
        """
        clear_sky_factor = 1.0 + max(-0.15, min(0.15, (temp - 29.0) * 0.01))
        return max(0.0, historical_solar_kw * clear_sky_factor)

    def _residual_std(self) -> Optional[float]:
        if self._model_artifact:
            metrics = self._model_artifact.get("metrics", {})
            return metrics.get("test_rmse_kw")
        return None

    @staticmethod
    def _confidence_bounds(pred_demand: float, residual_std: Optional[float]) -> (float, float):
        if residual_std:
            # ~95% interval around the point forecast, from the model's held-out test error.
            half_width = 1.96 * residual_std
            return max(0.0, pred_demand - half_width), pred_demand + half_width
        # No trained model yet: a wider, asymmetric band reflecting greater uncertainty
        # on the upside (demand spikes are costlier to under-predict than over-predict).
        lower = pred_demand - (0.05 * pred_demand + 5.0)
        upper = pred_demand + (0.07 * pred_demand + 8.0)
        return max(0.0, lower), upper
