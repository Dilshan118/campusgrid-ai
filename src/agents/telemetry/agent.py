"""
CampusGrid AI: Agent 1 — Telemetry and Forecasting (ML · Data)
Ingests historical meter readings, fetches weather forecast, and projects 24-hour demand & solar PV profiles.
"""

from typing import Dict, Any, List, Optional
from src.agents.base.agent import BaseAgent
from src.domain.interfaces.repositories import MeterHistoryRepository, TimetableRepository
from src.domain.interfaces.tool import Tool
from src.domain.interfaces.forecaster import DemandForecasterInterface
from src.domain.interfaces.llm import LLMProvider
from src.domain.entities.telemetry import TelemetryInterval
from src.agents.telemetry.forecaster import DemandForecaster
from src.agents.telemetry.summary import build_forecast_summary
from src.agents.telemetry.privacy import add_privacy_noise_batch

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

    def _run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        target_date = input_data.get("date", "2026-09-06")
        room_id = input_data.get("room", "LH-1")

        # 1. Fetch historical benchmark meter intervals
        historical = self.meter_repo.get_historical_profile(target_date)

        # 2. Fetch ambient temperature series from weather tool
        weather_res = self.weather_tool.execute(date=target_date)
        temp_series = weather_res.data.get("temperature_series_c", [28.0] * len(historical))

        # 3. Fetch scheduled lecture occupancy
        occupancies = []
        for item in historical:
            occ = self.timetable_repo.get_room_occupancy(room_id, item.time_slot, day_of_week=1)
            occupancies.append(occ or item.zone_occupancy_count)

        # 4. Compute forecast
        forecast = self.forecaster.predict(historical, temp_series, occupancies)

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
            "occupancy_counts": occupancies,
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
        """
        historical = self.meter_repo.get_historical_profile(target_date)
        return add_privacy_noise_batch(historical, epsilon=epsilon)
