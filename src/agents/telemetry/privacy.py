"""
CampusGrid AI: Agent 1 — Meter Reading Privacy Protection
Module Owner: Member 2 (Telemetry, Data Engineering & Machine Learning)

Adds calibrated differential-privacy noise to meter readings before they leave
this layer, so a party observing exported telemetry cannot reliably reconstruct
exact sub-meter power draw (which is what enables NILM-style appliance/occupant
disaggregation attacks — see Student 2's red-team audit).

Uses the Laplace mechanism: for a query with sensitivity `sensitivity_kw` (the
maximum a single reading can change if one interval is added/removed/altered)
and privacy budget `epsilon`, adding Laplace(0, sensitivity/epsilon) noise gives
epsilon-differential privacy for that query.
"""

import math
import random
from typing import List
from src.domain.entities.telemetry import TelemetryInterval

DEFAULT_EPSILON = 1.0
DEFAULT_SENSITIVITY_KW = 15.0


def _laplace_noise(scale: float, rng: random.Random) -> float:
    """Samples Laplace(0, scale) noise via inverse-CDF sampling from U(-0.5, 0.5)."""
    u = rng.uniform(-0.5, 0.5)
    return -scale * math.copysign(1.0, u) * math.log(1.0 - 2.0 * abs(u) + 1e-12)


def add_privacy_noise(
    reading: TelemetryInterval,
    epsilon: float = DEFAULT_EPSILON,
    sensitivity_kw: float = DEFAULT_SENSITIVITY_KW,
    seed: int = None
) -> TelemetryInterval:
    """
    Returns a copy of `reading` with Laplace(epsilon, sensitivity) noise applied to
    base_load_kw and solar_gen_kw. Values are clamped at 0 kW (power cannot go negative)
    and rounded to 1 decimal place, which also thins the fine-grained signal an NILM
    attacker would need to fingerprint individual appliances.
    """
    rng = random.Random(seed) if seed is not None else random.Random()
    scale = sensitivity_kw / max(epsilon, 1e-6)

    noisy_load = max(0.0, reading.base_load_kw + _laplace_noise(scale, rng))
    noisy_solar = max(0.0, reading.solar_gen_kw + _laplace_noise(scale, rng))

    return TelemetryInterval(
        time_slot=reading.time_slot,
        base_load_kw=round(noisy_load, 1),
        solar_gen_kw=round(noisy_solar, 1),
        outdoor_temp_c=reading.outdoor_temp_c,
        grid_tariff_lkr_kwh=reading.grid_tariff_lkr_kwh,
        zone_occupancy_count=reading.zone_occupancy_count,
    )


def add_privacy_noise_batch(
    readings: List[TelemetryInterval],
    epsilon: float = DEFAULT_EPSILON,
    sensitivity_kw: float = DEFAULT_SENSITIVITY_KW,
    seed: int = None
) -> List[TelemetryInterval]:
    """Applies `add_privacy_noise` across a full 48-interval series."""
    rng = random.Random(seed) if seed is not None else random.Random()
    return [
        add_privacy_noise(r, epsilon=epsilon, sensitivity_kw=sensitivity_kw, seed=rng.randint(0, 2**31))
        for r in readings
    ]
