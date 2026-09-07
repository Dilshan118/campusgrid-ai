"""
Unit tests for Member 2 (Agent 1: Telemetry & Forecasting).
Terminal Command to run:
    pytest tests/unit/test_member2_telemetry.py -v
"""

import pytest
from src.agents.telemetry.forecaster import DemandForecaster
from src.domain.entities.telemetry import TelemetryInterval, PowerForecast

def test_member2_forecaster_contract():
    forecaster = DemandForecaster()

    # Generate synthetic 48-interval historical benchmark
    sample_intervals = [
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
    temps = [30.0] * 48
    occupancies = [60] * 48

    try:
        result = forecaster.predict(sample_intervals, temps, occupancies)
    except NotImplementedError:
        pytest.skip("Member 2 has not implemented DemandForecaster.predict() yet.")

    assert isinstance(result, PowerForecast)
    assert len(result.time_slots) == 48
    assert len(result.forecast_demand_kw) == 48
    assert len(result.forecast_solar_kw) == 48
    assert len(result.lower_bound_kw) == 48
    assert len(result.upper_bound_kw) == 48

    # Confidence interval checks: lower <= forecast <= upper
    for low, val, up in zip(result.lower_bound_kw, result.forecast_demand_kw, result.upper_bound_kw):
        assert low <= val <= up, f"Confidence bound violation: {low} <= {val} <= {up}"
