"""
CampusGrid AI: Datetime & Interval Utilities
Helpers for working with 48 half-hour microgrid time slots.
"""

from typing import Dict, List, Optional, Tuple

def get_standard_48_time_slots() -> List[str]:
    """Returns the standard 48 half-hour slots from '00:00' to '23:30'."""
    slots = []
    for hour in range(24):
        slots.append(f"{hour:02d}:00")
        slots.append(f"{hour:02d}:30")
    return slots

def time_slot_to_index(slot: str) -> int:
    """Converts 'HH:MM' string to 0..47 interval index."""
    parts = slot.split(":")
    hour = int(parts[0])
    minute = int(parts[1])
    return hour * 2 + (1 if minute >= 30 else 0)

def index_to_time_slot(idx: int) -> str:
    """Converts 0..47 interval index to 'HH:MM' string."""
    hour = idx // 2
    minute = 30 if (idx % 2 == 1) else 0
    return f"{hour:02d}:{minute:02d}"

def is_peak_hour(slot: str) -> bool:
    """Returns True if time slot falls within the PUCSL Peak Tariff window (18:00 - 22:30)."""
    idx = time_slot_to_index(slot)
    # 18:00 is idx 36, 22:00 is idx 44, 22:30 is idx 45
    return 36 <= idx <= 44

def _window_bounds(window: str) -> Tuple[int, int]:
    """'18:00 - 22:30' -> (36, 45): half-open range of slot indices the window covers."""
    start, end = [part.strip() for part in window.split("-")]
    return time_slot_to_index(start), time_slot_to_index(end)


def _in_window(idx: int, bounds: Tuple[int, int]) -> bool:
    start, end = bounds
    if start <= end:
        return start <= idx < end
    return idx >= start or idx < end  # window wraps past midnight


def get_tou_tariff_for_slot(
    slot: str,
    peak_rate: float,
    day_rate: float,
    off_peak_rate: float,
    peak_window: str = "18:00 - 22:30",
    day_window: str = "05:30 - 18:00",
) -> float:
    """Returns appropriate TOU rate in LKR/kWh for the given 30-min time slot.

    Anything outside the peak and day windows is billed at the off-peak rate.
    """
    idx = time_slot_to_index(slot)
    if _in_window(idx, _window_bounds(peak_window)):
        return peak_rate
    if _in_window(idx, _window_bounds(day_window)):
        return day_rate
    return off_peak_rate


def build_tou_tariff_profile(
    time_slots: List[str],
    peak_rate: float,
    day_rate: float,
    off_peak_rate: float,
    windows: Optional[Dict[str, str]] = None,
) -> List[float]:
    """Generates the per-interval tariff list matching the provided time slots.

    `windows` is the {"peak": "HH:MM - HH:MM", "day": ...} map Agent 3 extracts from the tariff
    documents; the PUCSL GP-2 reference windows are used for any window not supplied.
    """
    windows = windows or {}
    peak_window = windows.get("peak", "18:00 - 22:30")
    day_window = windows.get("day", "05:30 - 18:00")
    return [
        get_tou_tariff_for_slot(slot, peak_rate, day_rate, off_peak_rate, peak_window, day_window)
        for slot in time_slots
    ]
