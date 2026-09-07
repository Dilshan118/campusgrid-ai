"""
CampusGrid AI: Datetime & Interval Utilities
Helpers for working with 48 half-hour microgrid time slots.
"""

from typing import List

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
