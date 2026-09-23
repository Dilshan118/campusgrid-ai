"""
CampusGrid AI: Agent 1 — Shared Forecasting Model Utilities
Module Owner: Member 2 (Telemetry, Data Engineering & Machine Learning)

Feature engineering and a dependency-free linear-model predictor shared by
`forecaster.py` (inference) and `src/pipelines/periodic_retraining/train_forecaster.py`
(training), so the two never drift apart.

Kept free of numpy/pandas/lightgbm imports on purpose: this module must import
cleanly even on a machine where the optional `ml` extras
(`pip install -e ".[ml]"`) have not been installed, because `forecaster.py`
uses it on the hot inference path.
"""

import math
from typing import List, Dict, Any, Optional

FEATURE_NAMES = ["hour_sin", "hour_cos", "outdoor_temp_c", "occupancy_count"]


def time_slot_to_hour_frac(time_slot: str) -> float:
    """Converts an 'HH:MM' slot label to a fractional hour (e.g. '14:30' -> 14.5)."""
    hour_str, minute_str = time_slot.split(":")
    return int(hour_str) + int(minute_str) / 60.0


def build_feature_vector(time_slot: str, outdoor_temp_c: float, occupancy_count: float) -> List[float]:
    """
    Builds the [hour_sin, hour_cos, outdoor_temp_c, occupancy_count] feature vector.

    Hour-of-day is encoded as sin/cos (rather than a raw 0-23 integer) so the model
    sees midnight and 23:30 as neighbours instead of the two ends of a number line.
    """
    hour_frac = time_slot_to_hour_frac(time_slot)
    angle = 2.0 * math.pi * hour_frac / 24.0
    return [math.sin(angle), math.cos(angle), float(outdoor_temp_c), float(occupancy_count)]


def standardize(vector: List[float], means: List[float], stds: List[float]) -> List[float]:
    return [
        (v - m) / s if s > 1e-9 else 0.0
        for v, m, s in zip(vector, means, stds)
    ]


def linear_predict(
    weights: List[float],
    bias: float,
    means: List[float],
    stds: List[float],
    feature_vector: List[float]
) -> float:
    """Predicts base_load_kw from a standardized linear model: bias + w . standardize(x)."""
    x = standardize(feature_vector, means, stds)
    return bias + sum(w * xi for w, xi in zip(weights, x))


def rmse(errors: List[float]) -> float:
    if not errors:
        return 0.0
    return math.sqrt(sum(e * e for e in errors) / len(errors))


def mae(errors: List[float]) -> float:
    if not errors:
        return 0.0
    return sum(abs(e) for e in errors) / len(errors)


class LinearForecastModel:
    """
    A minimal multiple-linear-regression predictor, serializable to/from plain JSON.

    Exists as the dependency-free fallback for environments where LightGBM /
    scikit-learn are unavailable (see `train_forecaster.py`). Once those libraries
    are installed, the trainer prefers a real gradient-boosted model instead and
    this class is not used for prediction — only as the offline safety net.
    """

    def __init__(self, weights: List[float], bias: float, means: List[float], stds: List[float]):
        self.weights = weights
        self.bias = bias
        self.means = means
        self.stds = stds

    def predict(self, feature_vector: List[float]) -> float:
        return linear_predict(self.weights, self.bias, self.means, self.stds, feature_vector)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_type": "linear_regression",
            "weights": self.weights,
            "bias": self.bias,
            "means": self.means,
            "stds": self.stds,
            "feature_names": FEATURE_NAMES,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "LinearForecastModel":
        return cls(
            weights=payload["weights"],
            bias=payload["bias"],
            means=payload["means"],
            stds=payload["stds"],
        )


def load_model_artifact(path: str) -> Optional[Dict[str, Any]]:
    """Loads a trained-model JSON artifact, returning None if it does not exist or is unreadable."""
    import json
    import os

    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
