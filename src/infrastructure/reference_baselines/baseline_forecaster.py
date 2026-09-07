"""
CampusGrid AI: Reference Baseline Forecaster
Statistical baseline model combining historical meter averages, temperature correlation, and scheduled occupancy.
Preserved as a reference benchmark for Member 2.
"""

from typing import List
from src.domain.entities.telemetry import TelemetryInterval, PowerForecast
from src.domain.interfaces.forecaster import DemandForecasterInterface

class BaselineDemandForecaster(DemandForecasterInterface):
    """Predictive baseline model for campus electricity demand."""

    def predict(
        self,
        historical_intervals: List[TelemetryInterval],
        temperature_series: List[float],
        occupancy_counts: List[int]
    ) -> PowerForecast:
        slots = []
        demands = []
        solars = []
        lowers = []
        uppers = []
        anomalies = []

        for idx, item in enumerate(historical_intervals):
            slot = item.time_slot
            temp = temperature_series[idx] if idx < len(temperature_series) else item.outdoor_temp_c
            occ = occupancy_counts[idx] if idx < len(occupancy_counts) else item.zone_occupancy_count

            # Temperature sensitivity factor: +15 kW per °C above 28°C (cooling load)
            cooling_delta = max(0.0, temp - 28.0) * 15.0
            occ_delta = occ * 0.05  # Extra equipment power per student

            pred_demand = round(item.base_load_kw + cooling_delta + occ_delta, 1)
            pred_solar = round(item.solar_gen_kw, 1)

            # 95% confidence bands (approx +/- 6%)
            lowers.append(round(pred_demand * 0.94, 1))
            uppers.append(round(pred_demand * 1.06, 1))

            slots.append(slot)
            demands.append(pred_demand)
            solars.append(pred_solar)

            # Anomaly check: baseline spike above 850 kW
            if pred_demand > 850.0:
                anomalies.append(idx)

        return PowerForecast(
            time_slots=slots,
            forecast_demand_kw=demands,
            forecast_solar_kw=solars,
            lower_bound_kw=lowers,
            upper_bound_kw=uppers,
            anomaly_indices=anomalies,
            model_version="v4.2-campus-hybrid-reference"
        )
