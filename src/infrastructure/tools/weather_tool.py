"""
CampusGrid AI: Weather Tool
Fetches ambient temperature and solar irradiance for campus coordinates from
Open-Meteo (free, no API key required), with in-process caching and an offline
fallback so the rest of the system never depends on the network being up.

Owner: Member 2 (Developer 1 - Telemetry & Machine Learning)
"""

import json
import random
import time
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional
from src.domain.interfaces.tool import Tool, ToolResult

OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT_SECONDS = 5.0
CACHE_TTL_SECONDS = 3600  # weather forecasts don't need refetching more than hourly

# Standard diurnal curve for a tropical campus (Malabe, Sri Lanka: ~25C night to ~33C noon).
# Used whenever Open-Meteo is unreachable, so tests and offline demos never depend on the internet.
FALLBACK_TEMPERATURE_CURVE_C: List[float] = [
    26.2, 26.0, 25.8, 25.7, 25.5, 25.4, 25.3, 25.2, 25.1, 25.2, 25.4, 25.8,
    26.5, 27.2, 28.0, 28.8, 29.5, 30.2, 30.8, 31.4, 32.0, 32.5, 33.0, 33.4,
    33.8, 34.0, 33.9, 33.5, 32.8, 32.0, 31.2, 30.5, 29.8, 29.2, 28.8, 28.4,
    28.1, 27.8, 27.5, 27.2, 27.0, 26.8, 26.6, 26.5, 26.4, 26.3, 26.2, 26.1
]


class WeatherTool(Tool):
    """Fetches outdoor temperature and weather for campus coordinates."""

    def __init__(self, latitude: float = 6.9147, longitude: float = 79.9733):
        self.latitude = latitude
        self.longitude = longitude
        self._cache: Dict[str, Dict[str, Any]] = {}

    @property
    def name(self) -> str:
        return "get_campus_weather_forecast"

    @property
    def description(self) -> str:
        return "Retrieves ambient outdoor temperature (°C) and solar conditions for 48 campus intervals."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format (defaults to current day)"
                }
            }
        }

    def execute(self, **kwargs) -> ToolResult:
        start_time = time.time()
        date_str: Optional[str] = kwargs.get("date")
        cache_key = date_str or "today"

        cached = self._get_cached(cache_key)
        if cached is not None:
            elapsed = (time.time() - start_time) * 1000.0
            return ToolResult(success=True, data={**cached, "source": "cache"}, execution_time_ms=elapsed)

        temperatures, source = self._fetch_temperatures(date_str)
        elapsed = (time.time() - start_time) * 1000.0

        data = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "temperature_series_c": temperatures,
            "intervals_count": len(temperatures),
            "source": source,
        }
        self._set_cached(cache_key, data)

        return ToolResult(success=True, data=data, execution_time_ms=elapsed)

    def _fetch_temperatures(self, date_str: Optional[str]) -> (List[float], str):
        """Calls Open-Meteo for a 48-half-hour temperature series; falls back offline on any failure."""
        url = (
            f"{OPEN_METEO_BASE_URL}"
            f"?latitude={self.latitude}&longitude={self.longitude}"
            f"&hourly=temperature_2m&forecast_days=2&timezone=auto"
        )
        if date_str:
            url += f"&start_date={date_str}&end_date={date_str}"

        try:
            request = urllib.request.Request(url, headers={"User-Agent": "CampusGridAI/4.2"})
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
            hourly_temps = payload["hourly"]["temperature_2m"][:24]
            if len(hourly_temps) < 24:
                raise ValueError("Open-Meteo returned fewer than 24 hourly readings")
            # Interpolate 24 hourly readings into 48 half-hourly slots.
            half_hourly = self._upsample_hourly_to_half_hourly(hourly_temps)
            return half_hourly, "open-meteo"
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError, OSError):
            return self._offline_fallback_curve(date_str), "offline-fallback"

    @staticmethod
    def _offline_fallback_curve(date_str: Optional[str]) -> List[float]:
        """
        Deterministically perturbs the base diurnal curve by a date-derived seed, so the
        fallback still returns different (but reproducible) values per date instead of an
        identical curve every day when Open-Meteo cannot be reached.
        """
        rng = random.Random(date_str or "today")
        daily_offset = rng.uniform(-1.5, 1.5)
        return [
            round(base_temp + daily_offset + rng.uniform(-0.4, 0.4), 1)
            for base_temp in FALLBACK_TEMPERATURE_CURVE_C
        ]

    @staticmethod
    def _upsample_hourly_to_half_hourly(hourly_temps: List[float]) -> List[float]:
        """Linearly interpolates 24 hourly readings into 48 half-hour slots."""
        half_hourly: List[float] = []
        for hour_idx in range(24):
            current = hourly_temps[hour_idx]
            nxt = hourly_temps[hour_idx + 1] if hour_idx + 1 < len(hourly_temps) else current
            half_hourly.append(round(current, 1))
            half_hourly.append(round((current + nxt) / 2.0, 1))
        return half_hourly

    def _get_cached(self, key: str) -> Optional[Dict[str, Any]]:
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.time() - entry["cached_at"] > CACHE_TTL_SECONDS:
            del self._cache[key]
            return None
        return entry["data"]

    def _set_cached(self, key: str, data: Dict[str, Any]) -> None:
        self._cache[key] = {"data": data, "cached_at": time.time()}
