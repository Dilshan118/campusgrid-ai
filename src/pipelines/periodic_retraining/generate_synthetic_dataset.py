"""
CampusGrid AI: Synthetic 90-Day Campus Telemetry Dataset Generator
Module Owner: Member 2 (Telemetry, Data Engineering & Machine Learning)

Generates `data/campus_90day_dataset.csv` — 90 days x 48 half-hour intervals of
synthetic meter history — for `train_forecaster.py` to train and evaluate against.

Why synthetic instead of Building Data Genome 2 (BDG2): this development
environment has no outbound internet access (verified: `pip install` and
`curl` both time out), so BDG2 cannot be downloaded here. See
`data/README.md` for the full list of generative assumptions, so an examiner
can see exactly how "real" this data is and is not.

Deterministic: re-running this script with the same DEFAULT_SEED reproduces
byte-identical output.
"""

import csv
import math
import os
import random
from datetime import date, timedelta
from typing import List, Tuple

DEFAULT_SEED = 20260101
NUM_DAYS = 90
INTERVALS_PER_DAY = 48
START_DATE = date(2026, 6, 1)

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "data", "campus_90day_dataset.csv")

CSV_COLUMNS = [
    "reading_date", "time_slot", "base_load_kw", "solar_gen_kw",
    "outdoor_temp_c", "grid_tariff_lkr_kwh", "zone_occupancy_count"
]


def _time_slot(interval_idx: int) -> str:
    hour = interval_idx // 2
    minute = 30 if interval_idx % 2 else 0
    return f"{hour:02d}:{minute:02d}"


def _tariff_for_hour(hour: int) -> float:
    """PUCSL-style time-of-use bands (matches the seed convention in InMemoryMeterHistoryRepository)."""
    if 18 <= hour < 23:
        return 58.0
    if hour < 6:
        return 15.0
    return 30.0


def _seasonal_temp_drift(day_idx: int) -> float:
    """Slow ~90-day drift, e.g. moving from an inter-monsoon lull into a hotter dry spell."""
    return 1.5 * math.sin(2.0 * math.pi * day_idx / NUM_DAYS)


def _diurnal_temp_curve(interval_idx: int) -> float:
    """Base tropical diurnal curve: coolest ~04:30, hottest ~14:00."""
    hour_frac = interval_idx / 2.0
    return 29.5 + 4.3 * math.sin(2.0 * math.pi * (hour_frac - 8.5) / 24.0)


def _occupancy_for_slot(day_of_week: int, interval_idx: int, rng: random.Random, event_day: bool) -> int:
    hour = interval_idx // 2
    is_weekend = day_of_week >= 5
    if is_weekend:
        base = 15 if 9 <= hour <= 16 else 5
    elif 8 <= hour <= 17:
        # Lunch dip between 12:00-13:00
        base = 90 if hour == 12 else 220
    else:
        base = 10
    if event_day and 9 <= hour <= 15:
        base += 300  # e.g. a convocation or open day filling the auditorium
    noise = rng.randint(-15, 15)
    return max(0, base + noise)


def _clear_sky_factor(day_idx: int, rng: random.Random) -> float:
    """One cloud-cover roll per day: occasional overcast/monsoon-influenced days reduce solar yield."""
    if rng.random() < 0.15:
        return rng.uniform(0.35, 0.6)  # overcast day
    return rng.uniform(0.85, 1.05)


def _solar_for_slot(interval_idx: int, clear_sky_factor: float) -> float:
    hour_frac = interval_idx / 2.0
    if hour_frac < 6.0 or hour_frac > 18.0:
        return 0.0
    daylight_phase = math.sin(math.pi * (hour_frac - 6.0) / 12.0)
    return max(0.0, 210.0 * daylight_phase * clear_sky_factor)


def generate_rows(seed: int = DEFAULT_SEED) -> List[List]:
    rng = random.Random(seed)
    rows: List[List] = []

    for day_idx in range(NUM_DAYS):
        current_date = START_DATE + timedelta(days=day_idx)
        day_of_week = current_date.weekday()  # Monday=0 .. Sunday=6
        event_day = rng.random() < 0.05  # ~1 special-event day every 3 weeks
        seasonal_drift = _seasonal_temp_drift(day_idx)
        clear_sky_factor = _clear_sky_factor(day_idx, rng)

        for interval_idx in range(INTERVALS_PER_DAY):
            hour = interval_idx // 2
            temp = _diurnal_temp_curve(interval_idx) + seasonal_drift + rng.uniform(-0.6, 0.6)
            temp = round(temp, 1)

            occupancy = _occupancy_for_slot(day_of_week, interval_idx, rng, event_day)

            # Physically-motivated demand model (kept consistent with the statistical
            # fallback in forecaster.py, so the trained model is learning a noisier,
            # more realistic version of the same underlying physics, not a different world).
            night_base_kw = 180.0
            weekday_daytime_kw = 0.0 if day_of_week >= 5 else (300.0 if 8 <= hour <= 17 else 0.0)
            cooling_delta = max(0.0, temp - 27.0) * 12.0
            occupancy_delta = occupancy * 0.08
            noise = rng.gauss(0.0, 8.0)
            base_load_kw = max(50.0, round(
                night_base_kw + weekday_daytime_kw + cooling_delta + occupancy_delta + noise, 1
            ))

            solar_gen_kw = round(_solar_for_slot(interval_idx, clear_sky_factor) + rng.gauss(0.0, 3.0), 1)
            solar_gen_kw = max(0.0, solar_gen_kw)

            tariff = _tariff_for_hour(hour)

            rows.append([
                current_date.isoformat(),
                _time_slot(interval_idx),
                base_load_kw,
                solar_gen_kw,
                temp,
                tariff,
                occupancy,
            ])

    return rows


def write_dataset(output_path: str = OUTPUT_PATH, seed: int = DEFAULT_SEED) -> str:
    rows = generate_rows(seed)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)
        writer.writerows(rows)
    return output_path


if __name__ == "__main__":
    path = write_dataset()
    print(f"Wrote {NUM_DAYS * INTERVALS_PER_DAY} rows ({NUM_DAYS} days) to {path}")
