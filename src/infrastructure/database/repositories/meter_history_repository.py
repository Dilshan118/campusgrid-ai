"""
CampusGrid AI: Meter History Repository Implementations
Adapters for historical sub-meter telemetry intervals.

OWNER: Member 2 (Developer 1 - Telemetry & Machine Learning)

A PostgresMeterHistoryRepository does not exist yet, so the DI container falls back to
the CSV-seeded in-memory store even when DATABASE_PROVIDER=postgres — meaning Agent 1
never reads Neon. Adding it is Developer 1's task; the `meter_history` table in
backend/data/init.sql now mirrors TelemetryInterval field-for-field.
"""

import os
import csv
from typing import List, Optional
from src.domain.interfaces.repositories import MeterHistoryRepository
from src.domain.entities.telemetry import TelemetryInterval


class InMemoryMeterHistoryRepository(MeterHistoryRepository):
    """In-memory historical meter log loaded from sample_campus_seed.csv."""

    def __init__(self, seed_csv_path: Optional[str] = None):
        self._records: List[TelemetryInterval] = []
        self._load_seed_data(seed_csv_path)

    def _load_seed_data(self, seed_csv_path: Optional[str]):
        paths = [
            seed_csv_path,
            "backend/data/seeds/sample_campus_seed.csv",
            "../backend/data/seeds/sample_campus_seed.csv",
            os.path.join(
                os.path.dirname(__file__),
                "../../../../backend/data/seeds/sample_campus_seed.csv"
            ),
        ]

        loaded = False
        for p in paths:
            if p and os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            self._records.append(TelemetryInterval(
                                time_slot=row["time_slot"],
                                base_load_kw=float(row["base_load_kw"]),
                                solar_gen_kw=float(row["solar_gen_kw"]),
                                outdoor_temp_c=float(row["outdoor_temp_c"]),
                                grid_tariff_lkr_kwh=float(row["grid_tariff_lkr_kwh"]),
                                zone_occupancy_count=int(row["zone_occupancy_count"])
                            ))
                    loaded = True
                    break
                except Exception:
                    continue

        if not loaded or len(self._records) == 0:
            # Synthetic 48-interval fallback if the seed CSV cannot be located.
            for h in range(24):
                for m in (0, 30):
                    slot = f"{h:02d}:{m:02d}"
                    base = 200.0 + (300.0 if 8 <= h <= 17 else 0.0)
                    solar = 150.0 if 9 <= h <= 15 else 0.0
                    temp = 26.0 + (5.0 if 10 <= h <= 15 else 0.0)
                    tariff = 58.0 if 18 <= h < 23 else (15.0 if h < 6 else 30.0)
                    self._records.append(TelemetryInterval(
                        time_slot=slot,
                        base_load_kw=base,
                        solar_gen_kw=solar,
                        outdoor_temp_c=temp,
                        grid_tariff_lkr_kwh=tariff,
                        zone_occupancy_count=100 if 8 <= h <= 16 else 10
                    ))

    def get_historical_profile(self, date_str: str) -> List[TelemetryInterval]:
        return list(self._records)

    def append_reading(self, reading: TelemetryInterval) -> bool:
        self._records.append(reading)
        return True
