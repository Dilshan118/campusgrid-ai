"""
CampusGrid AI: Meter History Repository Implementations
Adapters for historical sub-meter telemetry intervals.

OWNER: Member 2 (Developer 1 - Telemetry & Machine Learning)

InMemoryMeterHistoryRepository serves the CSV seed day (the same 48 rows for every date);
PostgresMeterHistoryRepository reads the `meter_history` table in backend/data/init.sql
(selected by DATABASE_PROVIDER=postgres), falling back to the seed day when a date has no rows.
"""

import os
import csv
from typing import List, Optional
from sqlalchemy import text
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


class PostgresMeterHistoryRepository(MeterHistoryRepository):
    """
    PostgreSQL implementation of MeterHistoryRepository, backed by the
    `meter_history` table defined in `backend/data/init.sql`. Column names mirror
    `TelemetryInterval` field-for-field, so rows round-trip without translation.

    Falls back to the in-memory CSV-seeded store if the table is empty for the
    requested date (e.g. a freshly-provisioned database before any real meter
    data has been ingested), so the system degrades gracefully instead of
    returning an empty forecast.
    """

    def __init__(self, engine, fallback: Optional[MeterHistoryRepository] = None):
        self.engine = engine
        self._fallback = fallback or InMemoryMeterHistoryRepository()

    def get_historical_profile(self, date_str: str) -> List[TelemetryInterval]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT time_slot, base_load_kw, solar_gen_kw, outdoor_temp_c, "
                    "grid_tariff_lkr_kwh, zone_occupancy_count "
                    "FROM meter_history WHERE reading_date = :date "
                    "ORDER BY time_slot;"
                ),
                {"date": date_str}
            ).fetchall()

        if not rows:
            return self._fallback.get_historical_profile(date_str)

        return [
            TelemetryInterval(
                time_slot=r[0],
                base_load_kw=r[1],
                solar_gen_kw=r[2],
                outdoor_temp_c=r[3],
                grid_tariff_lkr_kwh=r[4],
                zone_occupancy_count=r[5],
            )
            for r in rows
        ]

    def append_reading(self, reading: TelemetryInterval, reading_date: Optional[str] = None) -> bool:
        import datetime
        date_str = reading_date or datetime.date.today().isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO meter_history "
                    "(reading_date, time_slot, base_load_kw, solar_gen_kw, outdoor_temp_c, "
                    "grid_tariff_lkr_kwh, zone_occupancy_count) "
                    "VALUES (:date, :slot, :load, :solar, :temp, :tariff, :occ) "
                    "ON CONFLICT (reading_date, time_slot) DO UPDATE SET "
                    "base_load_kw = EXCLUDED.base_load_kw, "
                    "solar_gen_kw = EXCLUDED.solar_gen_kw, "
                    "outdoor_temp_c = EXCLUDED.outdoor_temp_c, "
                    "grid_tariff_lkr_kwh = EXCLUDED.grid_tariff_lkr_kwh, "
                    "zone_occupancy_count = EXCLUDED.zone_occupancy_count;"
                ),
                {
                    "date": date_str,
                    "slot": reading.time_slot,
                    "load": reading.base_load_kw,
                    "solar": reading.solar_gen_kw,
                    "temp": reading.outdoor_temp_c,
                    "tariff": reading.grid_tariff_lkr_kwh,
                    "occ": reading.zone_occupancy_count,
                }
            )
        return True
