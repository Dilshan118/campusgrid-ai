"""
CampusGrid AI: Agent 2 — Solar Irradiance and Solar Heat Gain
Module Owner: Member 3 (Digital Twin, Cyber-Physical Physics & Simulation)

Supplies Q_solar for the 2R2C model: the sun's heat entering a room through its glazing.

    Q_solar(t) = G(t) * A_eff        [kW]  with  G in kW/m2 and A_eff in m2

G(t) is global horizontal irradiance on the campus for the given date, from solar geometry
(declination, equation of time, hour angle at the campus longitude) and the Haurwitz
clear-sky model, G_clear = 1.098 * cos(Z) * exp(-0.057 / cos(Z)) kW/m2. A tropical coastal
sky is rarely clear, so the "typical day" irradiance is G_clear x TYPICAL_CLEARNESS. A solar
dropout (cloud cover, monsoon) lowers it further by the what-if's solar scaling factor.

A_eff, the effective solar aperture, comes per seat from the room preset (room_presets.py):
floor area x glazing share x solar heat-gain coefficient x the fraction of horizontal
irradiance a vertical window receives. Those are documented engineering estimates.

The weather feed carries only air temperature, so irradiance is computed here, not fetched.
Swapping in measured irradiance (a pyranometer, or a weather API's shortwave radiation) only
means passing `solar_irradiance_kw_m2` to the agent instead of relying on this default.
"""

import math
from datetime import date
from typing import List

# Campus coordinates, matching the weather tool's defaults.
CAMPUS_LATITUDE_DEG = 6.9147
CAMPUS_LONGITUDE_DEG = 79.9733
# Sri Lanka Standard Time is UTC+05:30, whose meridian is 82.5 degE.
_STANDARD_MERIDIAN_DEG = 82.5

# Share of clear-sky irradiance that reaches the ground on a typical day in western Sri Lanka,
# where humid haze and scattered cloud are the norm. An engineering estimate.
TYPICAL_CLEARNESS = 0.75

# Each interval's irradiance is the mean of this many evenly spaced samples inside it, so the
# sunrise and sunset intervals, where the sun is up for only part of the half-hour, are right.
_SAMPLES_PER_INTERVAL = 6


def _cos_zenith(day_of_year: int, clock_hour: float, latitude_deg: float, longitude_deg: float) -> float:
    declination = math.radians(23.45 * math.sin(math.radians(360.0 / 365.0 * (284 + day_of_year))))
    b = math.radians(360.0 * (day_of_year - 81) / 364.0)
    equation_of_time_min = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)
    solar_hour = clock_hour + (4.0 * (longitude_deg - _STANDARD_MERIDIAN_DEG) + equation_of_time_min) / 60.0
    hour_angle = math.radians(15.0 * (solar_hour - 12.0))
    lat = math.radians(latitude_deg)
    return math.sin(lat) * math.sin(declination) + math.cos(lat) * math.cos(declination) * math.cos(hour_angle)


def clear_sky_irradiance_kw_m2(
    day: date,
    n_intervals: int = 48,
    dt_hours: float = 0.5,
    latitude_deg: float = CAMPUS_LATITUDE_DEG,
    longitude_deg: float = CAMPUS_LONGITUDE_DEG,
) -> List[float]:
    """Mean clear-sky global horizontal irradiance (kW/m2) in each interval of `day`, from 00:00."""
    n = day.timetuple().tm_yday
    series: List[float] = []
    for i in range(n_intervals):
        total = 0.0
        for k in range(_SAMPLES_PER_INTERVAL):
            clock_hour = (i + (k + 0.5) / _SAMPLES_PER_INTERVAL) * dt_hours
            cos_z = _cos_zenith(n, clock_hour, latitude_deg, longitude_deg)
            if cos_z > 0.0:
                total += 1.098 * cos_z * math.exp(-0.057 / cos_z)
        series.append(round(total / _SAMPLES_PER_INTERVAL, 4))
    return series


def typical_irradiance_kw_m2(
    day: date,
    n_intervals: int = 48,
    dt_hours: float = 0.5,
    clearness: float = TYPICAL_CLEARNESS,
) -> List[float]:
    """Irradiance on a typical (hazy, part-cloudy) day at the campus."""
    return [round(g * clearness, 4) for g in clear_sky_irradiance_kw_m2(day, n_intervals, dt_hours)]


def solar_heat_gain_kw(irradiance_kw_m2: List[float], aperture_m2: float) -> List[float]:
    """Q_solar per interval for a room with effective solar aperture `aperture_m2`."""
    return [round(max(0.0, g) * aperture_m2, 3) for g in irradiance_kw_m2]
