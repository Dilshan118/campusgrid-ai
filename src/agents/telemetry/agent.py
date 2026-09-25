"""
CampusGrid AI: Agent 1 — Telemetry and Forecasting (ML · Data)
Ingests historical meter readings, fetches weather forecast, and projects 24-hour demand & solar PV profiles.
"""

import threading
from datetime import date
from typing import Dict, Any, List, Optional, Tuple
from src.agents.base.agent import BaseAgent
from src.domain.exceptions.base import DomainException
from src.domain.interfaces.repositories import MeterHistoryRepository, TimetableRepository
from src.domain.interfaces.tool import Tool
from src.domain.interfaces.forecaster import DemandForecasterInterface
from src.domain.interfaces.llm import LLMProvider
from src.domain.entities.telemetry import TelemetryInterval
from src.agents.telemetry.forecaster import DemandForecaster
from src.agents.telemetry.summary import build_forecast_summary
from src.agents.telemetry.privacy import add_privacy_noise_batch

# Noisy exports kept per (date, epsilon): serving fresh noise on every request would let a caller
# average repeated requests back to the exact readings, defeating the differential privacy.
_MAX_CACHED_EXPORTS = 512


def _iso_weekday(target_date: str) -> int:
    """Timetable day_of_week convention: 1 = Monday ... 7 = Sunday."""
    try:
        return date.fromisoformat(target_date).isoweekday()
    except (TypeError, ValueError):
        raise DomainException(
            message=f"'{target_date}' is not a valid date (expected YYYY-MM-DD).",
            error_code="VALIDATION_ERROR",
            details={"status": 422, "field": "date"},
        )


def _scheduled_occupancy(room_id: str, time_slot: str, schedule: List[Dict[str, Any]]) -> int:
    """Same rule as TimetableRepository.get_room_occupancy, over one pre-fetched day."""
    for entry in schedule:
        if entry["room_id"] == room_id and entry["start_time"] <= time_slot <= entry["end_time"]:
            return int(entry["expected_students"])
    return 0

class TelemetryForecastingAgent(BaseAgent):
    """Agent 1: Predicts day-ahead electricity demand and solar generation."""

    def __init__(
        self,
        meter_repo: MeterHistoryRepository,
        timetable_repo: TimetableRepository,
        weather_tool: Tool,
        forecaster: Optional[DemandForecasterInterface] = None,
        llm_provider: Optional[LLMProvider] = None
    ):
        super().__init__(
            name="Agent 1: Telemetry & Forecasting",
            description="Predicts day-ahead load (kW) and solar PV generation with confidence intervals."
        )
        self.meter_repo = meter_repo
        self.timetable_repo = timetable_repo
        self.weather_tool = weather_tool
        self.forecaster = forecaster or DemandForecaster()
        # Optional: enables the one-sentence forecast summary (NLP "summarisation" mark).
        # Agent 1 works identically without it — see build_forecast_summary().
        self.llm_provider = llm_provider
        self._export_cache: Dict[Tuple[str, float], List[TelemetryInterval]] = {}
        self._export_lock = threading.Lock()

    def _run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        target_date = input_data.get("date") or date.today().isoformat()
        room_id = input_data.get("room", "LH-1")
        day_of_week = _iso_weekday(target_date)

        # 1. Fetch historical benchmark meter intervals
        historical = self.meter_repo.get_historical_profile(target_date)

        # 2. Fetch ambient temperature series from weather tool
        weather_res = self.weather_tool.execute(date=target_date)
        temp_series = weather_res.data.get("temperature_series_c", [28.0] * len(historical))

        # 3. Occupancy. The forecaster predicts CAMPUS demand, so it gets the campus headcount it
        #    was trained on (meter history). The room's own timetable, for the target weekday, is
        #    what the digital twin simulates. One timetable query for the day, not one per slot.
        schedule = self.timetable_repo.get_schedule_for_day(day_of_week)
        room_occupancy = [_scheduled_occupancy(room_id, item.time_slot, schedule) for item in historical]
        campus_occupancy = [item.zone_occupancy_count for item in historical]

        # 4. Compute forecast
        forecast = self.forecaster.predict(historical, temp_series, campus_occupancy)

        # 5. Plain-English forecast summary (one LLM call; every number in it comes
        #    from `forecast` above, never from the model's own memory).
        forecast_summary = build_forecast_summary(
            llm_provider=self.llm_provider,
            time_slots=forecast.time_slots,
            forecast_demand_kw=forecast.forecast_demand_kw,
            temperature_series_c=temp_series,
            anomaly_indices=forecast.anomaly_indices,
        )

        return {
            "target_date": target_date,
            "time_slots": forecast.time_slots,
            "forecast_demand_kw": forecast.forecast_demand_kw,
            "forecast_solar_kw": forecast.forecast_solar_kw,
            "lower_bound_kw": forecast.lower_bound_kw,
            "upper_bound_kw": forecast.upper_bound_kw,
            "ambient_temperatures_c": temp_series,
            "occupancy_counts": room_occupancy,
            "campus_occupancy_counts": campus_occupancy,
            "day_of_week": day_of_week,
            "anomaly_count": len(forecast.anomaly_indices),
            "tariffs_lkr_kwh": [item.grid_tariff_lkr_kwh for item in historical],
            "forecast_summary": forecast_summary,
        }

    def get_privacy_protected_export(
        self,
        target_date: str,
        epsilon: float = 1.0
    ) -> List[TelemetryInterval]:
        """
        Returns the day's meter history with calibrated differential-privacy (Laplace)
        noise applied, for any consumer outside this agent's trust boundary (dashboards,
        analytics exports, third-party reports). Internal forecasting never calls this —
        `_run()` always uses the raw historical profile, so noise added for external
        sharing never degrades the forecaster's own accuracy.

        The noisy values are fixed per date for the life of the process: repeated requests get the
        same answer, so averaging many requests does not wash the noise out.
        """
        key = (target_date, float(epsilon))
        with self._export_lock:
            cached = self._export_cache.get(key)
        if cached is not None:
            return list(cached)
        noisy = add_privacy_noise_batch(self.meter_repo.get_historical_profile(target_date), epsilon=epsilon)
        with self._export_lock:
            # First writer wins, so concurrent requests for a date all see the same noisy values.
            cached = self._export_cache.setdefault(key, noisy)
            while len(self._export_cache) > _MAX_CACHED_EXPORTS:
                self._export_cache.pop(next(iter(self._export_cache)))
        return list(cached)
