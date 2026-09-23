"""
Unit tests for Member 2 (Agent 1: Telemetry & Forecasting).
Terminal Command to run:
    pytest tests/unit/test_member2_telemetry.py -v
"""

import os
import statistics

import pytest

from src.agents.telemetry.forecaster import DemandForecaster
from src.agents.telemetry.privacy import add_privacy_noise, add_privacy_noise_batch
from src.agents.telemetry.summary import build_forecast_summary
from src.agents.telemetry.agent import TelemetryForecastingAgent
from src.infrastructure.tools.weather_tool import WeatherTool
from src.infrastructure.database.repositories.meter_history_repository import InMemoryMeterHistoryRepository
from src.infrastructure.database.repositories.timetable_repository import InMemoryTimetableRepository
from src.domain.entities.telemetry import TelemetryInterval, PowerForecast
from src.pipelines.periodic_retraining.train_forecaster import ModelTrainer


def _sample_intervals():
    return [
        TelemetryInterval(
            time_slot=f"{h:02d}:{m:02d}",
            base_load_kw=350.0 + (100.0 if 8 <= h <= 17 else 0.0),
            solar_gen_kw=150.0 if 9 <= h <= 15 else 0.0,
            outdoor_temp_c=29.5,
            zone_occupancy_count=60,
            grid_tariff_lkr_kwh=30.0
        )
        for h in range(24) for m in (0, 30)
    ]


def test_member2_forecaster_contract():
    forecaster = DemandForecaster()
    sample_intervals = _sample_intervals()
    temps = [30.0] * 48
    occupancies = [60] * 48

    result = forecaster.predict(sample_intervals, temps, occupancies)

    assert isinstance(result, PowerForecast)
    assert len(result.time_slots) == 48
    assert len(result.forecast_demand_kw) == 48
    assert len(result.forecast_solar_kw) == 48
    assert len(result.lower_bound_kw) == 48
    assert len(result.upper_bound_kw) == 48

    for low, val, up in zip(result.lower_bound_kw, result.forecast_demand_kw, result.upper_bound_kw):
        assert low <= val <= up, f"Confidence bound violation: {low} <= {val} <= {up}"


def test_forecaster_flags_extreme_heat_as_anomalous():
    """A room with a 40C spike and heavy occupancy should be flagged as anomalous."""
    forecaster = DemandForecaster()
    sample_intervals = _sample_intervals()
    temps = [30.0] * 47 + [42.0]
    occupancies = [60] * 47 + [400]

    result = forecaster.predict(sample_intervals, temps, occupancies)
    assert 47 in result.anomaly_indices


def test_forecaster_never_predicts_negative_demand_or_solar():
    forecaster = DemandForecaster()
    sample_intervals = _sample_intervals()
    temps = [-5.0] * 48  # implausible, but must not break the safety property
    occupancies = [0] * 48

    result = forecaster.predict(sample_intervals, temps, occupancies)
    assert all(v >= 0.0 for v in result.forecast_demand_kw)
    assert all(v >= 0.0 for v in result.forecast_solar_kw)
    assert all(v >= 0.0 for v in result.lower_bound_kw)


def test_forecaster_uses_trained_model_artifact_when_present(tmp_path):
    """If a trained model JSON exists at the given path, the forecaster must use it (not the statistical fallback)."""
    import json

    model_path = tmp_path / "model_forecaster.json"
    model_path.write_text(json.dumps({
        "model_type": "linear_regression",
        "weights": [1.0, 1.0, 2.0, 0.1],
        "bias": 100.0,
        "means": [0.0, 0.0, 28.0, 50.0],
        "stds": [1.0, 1.0, 3.0, 20.0],
        "metrics": {"test_rmse_kw": 12.5},
    }))

    forecaster = DemandForecaster(model_path=str(model_path))
    assert forecaster._model_artifact is not None
    assert "linear_regression" in forecaster.predict(_sample_intervals(), [30.0] * 48, [60] * 48).model_version


def test_forecaster_falls_back_gracefully_when_no_model_artifact_exists():
    forecaster = DemandForecaster(model_path="this/path/does/not/exist.json")
    assert forecaster._model_artifact is None
    result = forecaster.predict(_sample_intervals(), [30.0] * 48, [60] * 48)
    assert "statistical-fallback" in result.model_version


# ---------------------------------------------------------------------------
# Weather tool
# ---------------------------------------------------------------------------

def test_weather_tool_returns_48_intervals_and_caches():
    tool = WeatherTool()
    result_1 = tool.execute(date="2026-09-06")
    assert result_1.success
    assert len(result_1.data["temperature_series_c"]) == 48

    result_2 = tool.execute(date="2026-09-06")
    assert result_2.data["source"] == "cache"


def test_weather_tool_gives_different_values_for_different_dates():
    tool = WeatherTool()
    series_a = tool.execute(date="2026-01-15").data["temperature_series_c"]
    series_b = tool.execute(date="2026-07-20").data["temperature_series_c"]
    assert series_a != series_b


# ---------------------------------------------------------------------------
# Privacy noise
# ---------------------------------------------------------------------------

def test_privacy_noise_batch_preserves_length_and_slot_order():
    intervals = _sample_intervals()
    noised = add_privacy_noise_batch(intervals, epsilon=1.0)
    assert len(noised) == len(intervals)
    assert [n.time_slot for n in noised] == [i.time_slot for i in intervals]


def test_privacy_noise_clamps_at_zero_and_stays_unbiased_on_average():
    reading = intervals_for_noise = _sample_intervals()[0]
    samples = [add_privacy_noise(reading, epsilon=1.0).base_load_kw for _ in range(200)]
    assert all(v >= 0.0 for v in samples)
    assert abs(statistics.mean(samples) - reading.base_load_kw) < 15.0


# ---------------------------------------------------------------------------
# Forecast summary (NLP summarisation mark)
# ---------------------------------------------------------------------------

def test_forecast_summary_returns_none_without_llm_provider():
    summary = build_forecast_summary(
        llm_provider=None,
        time_slots=["00:00"],
        forecast_demand_kw=[100.0],
        temperature_series_c=[28.0],
        anomaly_indices=[],
    )
    assert summary is None


def test_agent_still_runs_without_llm_provider_and_omits_summary():
    agent = TelemetryForecastingAgent(
        meter_repo=InMemoryMeterHistoryRepository(),
        timetable_repo=InMemoryTimetableRepository(),
        weather_tool=WeatherTool(),
    )
    result = agent.execute({"date": "2026-09-06", "room": "LH-1"})
    assert result.success
    assert result.data["forecast_summary"] is None


# ---------------------------------------------------------------------------
# Training pipeline
# ---------------------------------------------------------------------------

def test_trainer_beats_baseline_on_the_synthetic_dataset(tmp_path):
    trainer = ModelTrainer()  # default data_path -> data/campus_90day_dataset.csv
    if not os.path.exists(trainer.data_path):
        pytest.skip("Synthetic dataset not generated; run generate_synthetic_dataset.py first.")

    output_path = str(tmp_path / "model_forecaster.json")
    metrics = trainer.train(output_model_path=output_path)

    assert os.path.exists(output_path)
    assert metrics["test_rmse_kw"] < metrics["baseline_test_rmse_kw"], (
        "Trained model must beat the simple statistical baseline on held-out days — "
        "this is the headline result for Developer 1's report."
    )
    assert metrics["n_test"] > 0
    assert metrics["n_train"] > metrics["n_test"]
