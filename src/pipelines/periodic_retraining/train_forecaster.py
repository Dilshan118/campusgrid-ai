"""
CampusGrid AI: Offline Model Retraining Pipeline (Agent 1 Telemetry)
Module Owner: Member 2 (Machine Learning & Data Pipelines)

RESPONSIBILITIES:
- Ingest historical campus telemetry (`data/campus_90day_dataset.csv` by default;
  see `data/README.md` for how that dataset was produced and why).
- Feature engineering: cyclic hour-of-day encoding, outdoor temperature, occupancy
  (shared with `src/agents/telemetry/forecaster.py` via `model_utils.py` so
  training and inference can never drift apart).
- Train a regression model to forecast `base_load_kw`, evaluated with RMSE and MAE
  on a time-based 20% held-out split, and compared against a simple statistical
  baseline (the headline result: "my model scores X, the baseline scores Y").
- Save the trained artifact for `forecaster.py` to load at inference time.

Model backend: prefers LightGBM/scikit-learn (`pip install -e ".[ml]"`) when
available. This development sandbox has no outbound internet access (verified:
`pip install` and `curl` to external hosts both time out), so those optional
libraries cannot be installed here. Rather than block on that, this trainer
falls back to a dependency-free multiple linear regression (gradient descent,
implemented in `model_utils.py`) so training, evaluation, and a real RMSE/MAE
comparison still run end-to-end in this environment. Once the `ml` extra is
installed on a machine with internet access, this file automatically prefers
LightGBM without any code changes.
"""

import csv
import json
import math
import os
import time
from datetime import date, timedelta
from typing import Dict, Any, List, Tuple

from src.domain.interfaces.forecaster import ForecasterTrainerInterface
from src.agents.telemetry.model_utils import (
    build_feature_vector,
    rmse,
    mae,
    LinearForecastModel,
)

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DEFAULT_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "campus_90day_dataset.csv")
# The JSON linear model that src/agents/telemetry/forecaster.py loads at inference time.
DEFAULT_MODEL_PATH = os.path.join(_REPO_ROOT, "src", "agents", "telemetry", "model_forecaster.json")
TEST_FRACTION = 0.2
# How far back the persistence baseline may look for the same half-hour's previous reading.
BASELINE_MAX_LOOKBACK_DAYS = 7

# Baseline coefficients, deliberately mirroring src/infrastructure/reference_baselines/baseline_forecaster.py
# so the "my model vs. the baseline" comparison is against the same baseline the rest of the team read as
# the reference implementation, not a straw man.
BASELINE_COOLING_THRESHOLD_C = 28.0
BASELINE_COOLING_KW_PER_C = 15.0
BASELINE_OCC_KW = 0.05


class ModelTrainer(ForecasterTrainerInterface):
    """Offline trainer for campus load and solar forecasting models."""

    def __init__(self, data_path: str = DEFAULT_DATA_PATH):
        self.data_path = data_path

    def train(self, output_model_path: str = DEFAULT_MODEL_PATH) -> Dict[str, Any]:
        rows = self._load_rows(self.data_path)
        if len(rows) < 20:
            raise ValueError(
                f"Not enough training rows ({len(rows)}) at {self.data_path}. "
                "Run `python src/pipelines/periodic_retraining/generate_synthetic_dataset.py` first, "
                "or point data_path at a real dataset."
            )

        train_rows, test_rows = self._time_based_split(rows, TEST_FRACTION)

        train_features = [self._features(r) for r in train_rows]
        train_targets = [r["base_load_kw"] for r in train_rows]
        test_features = [self._features(r) for r in test_rows]
        test_targets = [r["base_load_kw"] for r in test_rows]

        model, backend = self._try_train_lightgbm(train_features, train_targets)
        if model is None:
            model = self._train_linear_regression(train_features, train_targets)
            backend = "linear_regression"

        if backend == "linear_regression":
            predictions = [model.predict(f) for f in test_features]
        else:
            predictions = list(model.predict(test_features))

        errors = [p - t for p, t in zip(predictions, test_targets)]
        model_rmse = rmse(errors)
        model_mae = mae(errors)

        baseline_predictions = self._baseline_predictions(rows, test_rows)
        baseline_errors = [p - t for p, t in zip(baseline_predictions, test_targets)]
        baseline_rmse = rmse(baseline_errors)
        baseline_mae = mae(baseline_errors)

        metrics = {
            "model_backend": backend,
            "n_train": len(train_rows),
            "n_test": len(test_rows),
            "test_rmse_kw": round(model_rmse, 3),
            "test_mae_kw": round(model_mae, 3),
            "baseline_test_rmse_kw": round(baseline_rmse, 3),
            "baseline_test_mae_kw": round(baseline_mae, 3),
            "rmse_improvement_pct": round(100.0 * (1.0 - model_rmse / baseline_rmse), 1) if baseline_rmse else None,
            "mae_improvement_pct": round(100.0 * (1.0 - model_mae / baseline_mae), 1) if baseline_mae else None,
            "baseline": "reference baseline: previous day's same-slot reading + cooling and occupancy adjustments",
            "trained_at_unix": time.time(),
            "data_path": os.path.relpath(self.data_path, _REPO_ROOT),
            # The forecaster clips inputs to these, so it never extrapolates beyond the training data.
            "feature_ranges": {
                "outdoor_temp_c": [min(r["outdoor_temp_c"] for r in train_rows), max(r["outdoor_temp_c"] for r in train_rows)],
                "occupancy_count": [min(r["zone_occupancy_count"] for r in train_rows), max(r["zone_occupancy_count"] for r in train_rows)],
            },
        }

        self._save_artifact(model, backend, metrics, output_model_path)
        return metrics

    # ------------------------------------------------------------------
    # Data loading & splitting
    # ------------------------------------------------------------------

    @staticmethod
    def _load_rows(data_path: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        if not os.path.exists(data_path):
            return rows
        with open(data_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append({
                    "reading_date": row["reading_date"],
                    "time_slot": row["time_slot"],
                    "base_load_kw": float(row["base_load_kw"]),
                    "solar_gen_kw": float(row["solar_gen_kw"]),
                    "outdoor_temp_c": float(row["outdoor_temp_c"]),
                    "grid_tariff_lkr_kwh": float(row["grid_tariff_lkr_kwh"]),
                    "zone_occupancy_count": int(row["zone_occupancy_count"]),
                })
        return rows

    @staticmethod
    def _time_based_split(
        rows: List[Dict[str, Any]], test_fraction: float
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Splits chronologically (last `test_fraction` of *days* held out) rather than a
        random shuffle, so the model is evaluated on genuinely unseen future days —
        a random split would leak same-day patterns between train and test.
        """
        ordered = sorted(rows, key=lambda r: (r["reading_date"], r["time_slot"]))
        unique_dates = sorted({r["reading_date"] for r in ordered})
        n_test_days = max(1, int(round(len(unique_dates) * test_fraction)))
        test_dates = set(unique_dates[-n_test_days:])

        train_rows = [r for r in ordered if r["reading_date"] not in test_dates]
        test_rows = [r for r in ordered if r["reading_date"] in test_dates]
        return train_rows, test_rows

    @staticmethod
    def _features(row: Dict[str, Any]) -> List[float]:
        return build_feature_vector(row["time_slot"], row["outdoor_temp_c"], row["zone_occupancy_count"])

    @staticmethod
    def _baseline_predictions(all_rows: List[Dict[str, Any]], test_rows: List[Dict[str, Any]]) -> List[float]:
        """
        Exactly src/infrastructure/reference_baselines/baseline_forecaster.py's formula: the
        previous day's reading for the same half-hour, plus its temperature and occupancy
        adjustments. (An earlier version used a synthetic day/night floor in place of the real
        previous reading, which made the baseline look worse than the reference really is.)
        """
        history = {(r["reading_date"], r["time_slot"]): r["base_load_kw"] for r in all_rows}
        predictions = []
        for row in test_rows:
            day = date.fromisoformat(row["reading_date"])
            previous = None
            for back in range(1, BASELINE_MAX_LOOKBACK_DAYS + 1):
                previous = history.get(((day - timedelta(days=back)).isoformat(), row["time_slot"]))
                if previous is not None:
                    break
            if previous is None:
                raise ValueError(
                    f"No reading for {row['time_slot']} in the {BASELINE_MAX_LOOKBACK_DAYS} days before "
                    f"{row['reading_date']}; the persistence baseline needs contiguous history."
                )
            cooling = max(0.0, row["outdoor_temp_c"] - BASELINE_COOLING_THRESHOLD_C) * BASELINE_COOLING_KW_PER_C
            occ = row["zone_occupancy_count"] * BASELINE_OCC_KW
            predictions.append(previous + cooling + occ)
        return predictions

    # ------------------------------------------------------------------
    # Model backends
    # ------------------------------------------------------------------

    @staticmethod
    def _try_train_lightgbm(features: List[List[float]], targets: List[float]):
        """Returns (model, 'lightgbm') if the ml extras are installed, else (None, None)."""
        try:
            import numpy as np
            import lightgbm as lgb
        except ImportError:
            return None, None

        X = np.array(features)
        y = np.array(targets)
        model = lgb.LGBMRegressor(n_estimators=200, max_depth=6, learning_rate=0.05, verbose=-1)
        model.fit(X, y)
        return model, "lightgbm"

    @staticmethod
    def _train_linear_regression(
        features: List[List[float]], targets: List[float],
        learning_rate: float = 0.15, iterations: int = 800, l2: float = 1e-3
    ) -> LinearForecastModel:
        n_features = len(features[0])
        n_samples = len(features)

        means = [sum(f[i] for f in features) / n_samples for i in range(n_features)]
        stds = []
        for i in range(n_features):
            variance = sum((f[i] - means[i]) ** 2 for f in features) / n_samples
            stds.append(math.sqrt(variance) if variance > 1e-9 else 1.0)

        standardized = [
            [(f[i] - means[i]) / stds[i] for i in range(n_features)]
            for f in features
        ]

        weights = [0.0] * n_features
        bias = sum(targets) / n_samples

        for _ in range(iterations):
            grad_w = [0.0] * n_features
            grad_b = 0.0
            for x, y in zip(standardized, targets):
                pred = bias + sum(w * xi for w, xi in zip(weights, x))
                error = pred - y
                for i in range(n_features):
                    grad_w[i] += error * x[i]
                grad_b += error

            for i in range(n_features):
                grad_w[i] = grad_w[i] / n_samples + l2 * weights[i]
                weights[i] -= learning_rate * grad_w[i]
            bias -= learning_rate * (grad_b / n_samples)

        return LinearForecastModel(weights=weights, bias=bias, means=means, stds=stds)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @staticmethod
    def _save_artifact(model, backend: str, metrics: Dict[str, Any], output_model_path: str) -> None:
        os.makedirs(os.path.dirname(output_model_path) or ".", exist_ok=True)

        stem = os.path.splitext(output_model_path)[0]
        if backend == "linear_regression":
            payload = model.to_dict()
            payload["metrics"] = metrics
            payload["feature_ranges"] = metrics["feature_ranges"]
            with open(stem + ".json", "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        else:
            # Never write a pickle into the .json path: forecaster.py would fail to parse it and
            # silently fall back to its formula. forecaster.py loads only the JSON linear model.
            import joblib
            joblib.dump(model, f"{stem}.{backend}.joblib")
            with open(f"{stem}.{backend}.metrics.json", "w", encoding="utf-8") as f:
                json.dump(metrics, f, indent=2)
            print(
                f"Saved the {backend} model to {stem}.{backend}.joblib. "
                "Note: forecaster.py serves only the JSON linear model, which is unchanged."
            )


if __name__ == "__main__":
    trainer = ModelTrainer()
    result = trainer.train()
    print(json.dumps(result, indent=2))
