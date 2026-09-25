"""
CampusGrid AI: Agent 2 — Grey-Box Physics Constant Calibration
Module Owner: Member 3 (Digital Twin, Cyber-Physical Physics & Simulation)

The 2R2C model in `thermal_model.py` ships with GUESSED constants (c_in=50.0 kWh/°C,
r_vent=2.5 °C/kW). This module fits both constants against measured indoor temperatures
(the wall constants c_wall, r_in and r_out are held at their defaults during the fit)
using `scipy.optimize.least_squares`, and reports how much more accurate the fitted
model is than the guessed one — this is Developer 2's headline result.

Real building-management-system temperature logs are not yet wired into the project
(Developer 1 owns telemetry ingestion, and no live campus deployment exists for a
coursework project). Until that feed exists, `generate_synthetic_reference_dataset()`
stands in for it: it drives the SAME 2R2C equations forward with a chosen "true" (R, C)
pair plus small Gaussian sensor noise, producing a labelled dataset with a known ground
truth. Fitting against it proves the calibration pipeline recovers the right physics and
gives an honest, reproducible number for "how much better than guessing" — the exact
question the report and viva ask. Swapping in real sensor readings later requires no
change to `fit_thermal_constants()`, only a different `measured_indoor_temps_c` input.
"""

import csv
import os
import random
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
from scipy.optimize import least_squares

from src.agents.digital_twin.thermal_model import BuildingThermalTwin

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SEED_CSV_PATH = os.path.join(_REPO_ROOT, "backend", "data", "seeds", "sample_campus_seed.csv")

GUESSED_C_IN = 50.0
GUESSED_R_VENT = 2.5


def load_ambient_temperatures(csv_path: str = SEED_CSV_PATH) -> List[float]:
    """Reads the 48 real half-hourly outdoor temperatures from the campus seed data."""
    ambient_temps: List[float] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ambient_temps.append(float(row["outdoor_temp_c"]))
    return ambient_temps


def single_zone_class_schedule(n_intervals: int, peak_occupants: int = 180) -> List[int]:
    """A documented, synthetic single-lecture-hall occupancy curve: empty overnight,
    filling for the 08:00-17:00 teaching day. Half-hour intervals starting at 00:00."""
    schedule = []
    for i in range(n_intervals):
        hour = i // 2
        if 8 <= hour < 17:
            schedule.append(peak_occupants)
        elif hour in (7, 17):
            schedule.append(peak_occupants // 2)
        else:
            schedule.append(0)
    return schedule


def office_hours_hvac_schedule(n_intervals: int) -> List[float]:
    """Same baseline cooling curve DigitalTwinAgent falls back to when no proposal is given."""
    return [35.0 if 8 <= (i // 2) <= 17 else 5.0 for i in range(n_intervals)]


def generate_synthetic_reference_dataset(
    true_c_in: float = 41.5,
    true_r_vent: float = 3.15,
    noise_std_c: float = 0.05,
    initial_temp_c: float = 24.0,
    seed: int = 42,
) -> Tuple[List[float], List[int], List[float], List[float]]:
    """Builds a labelled calibration dataset with a KNOWN ground truth (true_c_in,
    true_r_vent), standing in for real sensor logs. Returns
    (ambient_temps, occupant_counts, hvac_power_kw, measured_indoor_temps_c).
    """
    ambient_temps = load_ambient_temperatures()
    occupant_counts = single_zone_class_schedule(len(ambient_temps))
    hvac_power_kw = office_hours_hvac_schedule(len(ambient_temps))

    true_twin = BuildingThermalTwin(c_in=true_c_in, r_vent=true_r_vent)
    clean_temps = true_twin.simulate(
        initial_temp_c=initial_temp_c,
        ambient_temps=ambient_temps,
        occupant_counts=occupant_counts,
        hvac_power_kw=hvac_power_kw,
    )

    rng = random.Random(seed)
    measured_temps = [round(t + rng.gauss(0.0, noise_std_c), 2) for t in clean_temps]

    return ambient_temps, occupant_counts, hvac_power_kw, measured_temps


@dataclass
class CalibrationResult:
    fitted_c_in: float
    fitted_r_vent: float
    guessed_c_in: float
    guessed_r_vent: float
    rmse_guessed: float
    rmse_fitted: float

    @property
    def accuracy_improvement_pct(self) -> float:
        if self.rmse_guessed == 0:
            return 0.0
        return round(100.0 * (self.rmse_guessed - self.rmse_fitted) / self.rmse_guessed, 1)


def _rmse(predicted: List[float], measured: List[float]) -> float:
    predicted_arr = np.asarray(predicted, dtype=float)
    measured_arr = np.asarray(measured, dtype=float)
    return float(np.sqrt(np.mean((predicted_arr - measured_arr) ** 2)))


def fit_thermal_constants(
    initial_temp_c: float,
    ambient_temps: List[float],
    occupant_counts: List[int],
    hvac_power_kw: List[float],
    measured_indoor_temps_c: List[float],
    initial_guess: Tuple[float, float] = (GUESSED_C_IN, GUESSED_R_VENT),
) -> CalibrationResult:
    """Fits (c_in, r_vent) against `measured_indoor_temps_c` with
    `scipy.optimize.least_squares`, and reports the accuracy gain over the guessed
    defaults this model previously shipped with.
    """

    def residuals(params: np.ndarray) -> np.ndarray:
        c_in, r_vent = params
        twin = BuildingThermalTwin(c_in=c_in, r_vent=r_vent)
        simulated = twin.simulate(
            initial_temp_c=initial_temp_c,
            ambient_temps=ambient_temps,
            occupant_counts=occupant_counts,
            hvac_power_kw=hvac_power_kw,
        )
        return np.asarray(simulated, dtype=float) - np.asarray(measured_indoor_temps_c, dtype=float)

    # `simulate()` rounds every step to 2 decimal places (realistic sensor-precision
    # output). The default finite-difference step scipy uses to estimate the Jacobian
    # is far smaller than that rounding resolution, so the numerical gradient comes out
    # as exactly zero and the optimizer falsely reports convergence at iteration 0.
    # `diff_step=1e-2` forces a perturbation large enough to clear the rounding floor.
    result = least_squares(
        residuals,
        x0=np.array(initial_guess, dtype=float),
        bounds=([0.01, 0.01], [np.inf, np.inf]),
        diff_step=1e-2,
    )
    fitted_c_in, fitted_r_vent = result.x

    guessed_twin = BuildingThermalTwin(c_in=initial_guess[0], r_vent=initial_guess[1])
    guessed_temps = guessed_twin.simulate(
        initial_temp_c=initial_temp_c,
        ambient_temps=ambient_temps,
        occupant_counts=occupant_counts,
        hvac_power_kw=hvac_power_kw,
    )

    fitted_twin = BuildingThermalTwin(c_in=fitted_c_in, r_vent=fitted_r_vent)
    fitted_temps = fitted_twin.simulate(
        initial_temp_c=initial_temp_c,
        ambient_temps=ambient_temps,
        occupant_counts=occupant_counts,
        hvac_power_kw=hvac_power_kw,
    )

    return CalibrationResult(
        fitted_c_in=round(float(fitted_c_in), 4),
        fitted_r_vent=round(float(fitted_r_vent), 4),
        guessed_c_in=initial_guess[0],
        guessed_r_vent=initial_guess[1],
        rmse_guessed=round(_rmse(guessed_temps, measured_indoor_temps_c), 4),
        rmse_fitted=round(_rmse(fitted_temps, measured_indoor_temps_c), 4),
    )


def run_calibration_report() -> CalibrationResult:
    """Convenience entry point: builds the synthetic reference dataset and fits against
    it. Run with `python -m src.agents.digital_twin.thermal_calibration` for the report
    used in the coursework write-up and viva.
    """
    ambient_temps, occupant_counts, hvac_power_kw, measured_temps = generate_synthetic_reference_dataset()
    return fit_thermal_constants(
        initial_temp_c=24.0,
        ambient_temps=ambient_temps,
        occupant_counts=occupant_counts,
        hvac_power_kw=hvac_power_kw,
        measured_indoor_temps_c=measured_temps,
    )


if __name__ == "__main__":
    report = run_calibration_report()
    print("Guessed constants:  c_in={:.2f} kWh/°C, r_vent={:.2f} °C/kW -> RMSE={:.4f} °C".format(
        report.guessed_c_in, report.guessed_r_vent, report.rmse_guessed
    ))
    print("Fitted constants:   c_in={:.4f} kWh/°C, r_vent={:.4f} °C/kW -> RMSE={:.4f} °C".format(
        report.fitted_c_in, report.fitted_r_vent, report.rmse_fitted
    ))
    print("Accuracy improvement: {:.1f}%".format(report.accuracy_improvement_pct))
