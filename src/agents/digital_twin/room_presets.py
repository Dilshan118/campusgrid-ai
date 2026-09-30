"""
CampusGrid AI: Agent 2 — Room-Type Physics Presets
Module Owner: Member 3 (Digital Twin, Cyber-Physical Physics & Simulation)

Maps a venue type ("Lecture Hall", "Computer Lab", "Study Area", ...) to 2R2C constants,
seating range and air-conditioning sizing. Used both for rooms listed in the campus
inventory (their room_type picks the preset, their max_capacity sets the size) and for a
custom room a facility manager describes because it is not listed.

Every quantity is PER SEAT, so each thermal mass and each heat path scales with the room:
a 600-seat auditorium has ~30x the air, structure, ventilation and envelope of a 20-seat
seminar room, and its time constants stay room-like instead of collapsing or exploding.
The per-seat figures are documented engineering estimates built from:

  - floor area per seat and ceiling height for the type  -> room volume
  - air + furnishings as ~5x the air's own heat capacity -> c_in   (fast node, ~15-30 min)
  - floor slab + partitions, ~0.15 kWh/degC per m2 floor -> c_wall (slow node, hours)
  - ASHRAE 62.1 outdoor air (per person + per m2), 0.5 ACH infiltration and single
    glazing at ~15% of floor area, U~5.7 W/m2K           -> g_vent (air <-> outdoor)
  - that glazing's solar heat gain (SHGC ~0.6, ~0.35 of
    horizontal irradiance on a vertical window)          -> solar_aperture_m2_per_seat
  - interior surfaces ~3x floor area at h~8 W/m2K         -> g_in   (air <-> structure)
  - external wall/roof share at U~1.5-2 W/m2K              -> g_out  (structure <-> outdoor)
  - lighting at ~10 W/m2 plus the type's equipment        -> equipment_kw_per_seat

The Lecture Hall's c_in and g_vent are the exception: they are the scipy-fitted constants
from thermal_calibration.py (see _LECTURE_HALL_FITTED_*), not estimates. Solar gain through
the glazing is Q_solar = irradiance x solar_aperture_m2 (see solar.py).
"""

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# A typical classroom split unit in Sri Lanka: 24,000 BTU/h = 7.0 kW of cooling.
AC_UNIT_COOLING_KW = 7.0

# thermal_calibration.run_calibration_report() for its 180-seat lecture hall. Kept in sync by
# test_member3_lecture_hall_preset_matches_calibration.
_LECTURE_HALL_CALIBRATION_SEATS = 180
_LECTURE_HALL_FITTED_C_IN = 1.3583
_LECTURE_HALL_FITTED_R_VENT = 0.7476

# A vertical window receives roughly this share of the irradiance on a horizontal surface over
# a tropical day, where the sun is high for most of it. An engineering estimate.
_VERTICAL_GLAZING_FACTOR = 0.35


def _solar_aperture_per_seat(floor_m2_per_seat: float, glazing_share: float, shgc: float) -> float:
    """Effective solar aperture (m2) per seat: the glazed area that lets the sun's heat in,
    weighted by how much of it passes the glass (SHGC) and reaches a vertical window."""
    return round(floor_m2_per_seat * glazing_share * shgc * _VERTICAL_GLAZING_FACTOR, 5)


@dataclass(frozen=True)
class RoomTypePreset:
    key: str
    label: str
    capacity_options: List[int]
    default_capacity: int
    c_in_per_seat: float          # kWh/degC — indoor air + furnishings
    c_wall_per_seat: float        # kWh/degC — slab and partitions
    g_vent_per_seat: float        # kW/degC  — ventilation, infiltration, glazing
    g_in_per_seat: float          # kW/degC  — air <-> interior surfaces
    g_out_per_seat: float         # kW/degC  — structure <-> outdoor
    equipment_kw_per_seat: float  # kW       — lighting + equipment while the room is in use
    solar_aperture_m2_per_seat: float  # m2    — effective glazing for solar heat gain
    seats_per_ac_unit: float      # sizing rule for the suggested AC count (with ~15% margin)
    notes: str


# Insertion order is the order the venue-type dropdown shows.
ROOM_TYPE_PRESETS: Dict[str, RoomTypePreset] = {
    "lecture_hall": RoomTypePreset(
        key="lecture_hall", label="Lecture Hall",
        capacity_options=[50, 100, 150, 200, 250], default_capacity=100,
        c_in_per_seat=round(_LECTURE_HALL_FITTED_C_IN / _LECTURE_HALL_CALIBRATION_SEATS, 6),
        c_wall_per_seat=0.15,
        g_vent_per_seat=round(1.0 / (_LECTURE_HALL_FITTED_R_VENT * _LECTURE_HALL_CALIBRATION_SEATS), 6),
        g_in_per_seat=0.024, g_out_per_seat=0.00145,
        equipment_kw_per_seat=0.012,  # lighting and a projector
        solar_aperture_m2_per_seat=_solar_aperture_per_seat(1.0, 0.15, 0.6),
        seats_per_ac_unit=35.0,
        notes="1 m2/seat, 4 m tiered ceiling. c_in and g_vent are fitted (thermal_calibration.py).",
    ),
    "computer_lab": RoomTypePreset(
        key="computer_lab", label="Computer Lab",
        capacity_options=[20, 40, 60, 80], default_capacity=40,
        c_in_per_seat=0.010, c_wall_per_seat=0.30,
        g_vent_per_seat=0.010, g_in_per_seat=0.048, g_out_per_seat=0.0029,
        equipment_kw_per_seat=0.14,  # a ~120 W desktop per seat plus lighting
        solar_aperture_m2_per_seat=_solar_aperture_per_seat(2.0, 0.15, 0.4),  # blinds drawn against screen glare
        seats_per_ac_unit=18.0,
        notes="2 m2/seat, 3 m ceiling. A PC per seat roughly doubles the heat each student brings.",
    ),
    "science_lab": RoomTypePreset(
        key="science_lab", label="Science Lab",
        capacity_options=[15, 25, 35], default_capacity=25,
        c_in_per_seat=0.016, c_wall_per_seat=0.45,
        g_vent_per_seat=0.022, g_in_per_seat=0.072, g_out_per_seat=0.0044,
        equipment_kw_per_seat=0.08,  # instruments, hot plates, lighting
        solar_aperture_m2_per_seat=_solar_aperture_per_seat(3.0, 0.15, 0.6),
        seats_per_ac_unit=15.0,
        notes="3 m2/seat. Fume-hood exhaust (~6 air changes/h) makes ventilation the dominant load.",
    ),
    "auditorium": RoomTypePreset(
        key="auditorium", label="Auditorium",
        capacity_options=[200, 400, 600], default_capacity=400,
        c_in_per_seat=0.012, c_wall_per_seat=0.20,
        g_vent_per_seat=0.0053, g_in_per_seat=0.030, g_out_per_seat=0.0020,
        equipment_kw_per_seat=0.014,  # stage lighting and AV
        solar_aperture_m2_per_seat=_solar_aperture_per_seat(0.9, 0.03, 0.6),  # almost windowless
        seats_per_ac_unit=35.0,
        notes="0.9 m2/seat, 8 m ceiling: a lot of air per seat, little glazing.",
    ),
    "study_area": RoomTypePreset(
        key="study_area", label="Study Area",
        capacity_options=[30, 60, 100, 150], default_capacity=60,
        c_in_per_seat=0.0147, c_wall_per_seat=0.375,
        g_vent_per_seat=0.0084, g_in_per_seat=0.060, g_out_per_seat=0.0036,
        equipment_kw_per_seat=0.055,  # laptop chargers and reading lights
        solar_aperture_m2_per_seat=_solar_aperture_per_seat(2.5, 0.15, 0.6),
        seats_per_ac_unit=24.0,
        notes="2.5 m2/seat, 3.5 m ceiling — library reading rooms and open study spaces.",
    ),
    "drawing_room": RoomTypePreset(
        key="drawing_room", label="Drawing Room",
        capacity_options=[20, 40, 60], default_capacity=40,
        c_in_per_seat=0.0176, c_wall_per_seat=0.45,
        g_vent_per_seat=0.0137, g_in_per_seat=0.072, g_out_per_seat=0.0044,
        equipment_kw_per_seat=0.05,  # drafting task lamps and a plotter
        solar_aperture_m2_per_seat=_solar_aperture_per_seat(3.0, 0.20, 0.6),  # extra glazing for daylight
        seats_per_ac_unit=20.0,
        notes="3 m2/seat for large drafting tables, 3.5 m ceiling.",
    ),
    "seminar_room": RoomTypePreset(
        key="seminar_room", label="Seminar Room",
        capacity_options=[10, 20, 30], default_capacity=20,
        c_in_per_seat=0.010, c_wall_per_seat=0.30,
        g_vent_per_seat=0.0064, g_in_per_seat=0.048, g_out_per_seat=0.0029,
        equipment_kw_per_seat=0.03,  # lighting and a screen
        solar_aperture_m2_per_seat=_solar_aperture_per_seat(2.0, 0.15, 0.6),
        seats_per_ac_unit=30.0,
        notes="2 m2/seat, 3 m ceiling.",
    ),
}

DEFAULT_ROOM_TYPE = "lecture_hall"

# Other spellings a room_type string might arrive with (from the rooms table, or a caller).
_ALIASES = {
    "laboratory": "science_lab",
    "science_laboratory": "science_lab",
    "computer_laboratory": "computer_lab",
    "computing_lab": "computer_lab",
    "lecture_theatre": "lecture_hall",
    "lecture_theater": "lecture_hall",
    "library": "study_area",
    "reading_room": "study_area",
    "study_room": "study_area",
    "drafting_room": "drawing_room",
    "drawing_studio": "drawing_room",
}


@dataclass(frozen=True)
class ResolvedRoomConfig:
    room_type: str
    label: str
    capacity: int
    num_acs: int
    ac_unit_cooling_kw: float
    total_hvac_capacity_kw: float
    equipment_heat_kw: float
    solar_aperture_m2: float
    c_in: float
    r_vent: float
    c_wall: float
    r_in: float
    r_out: float


def _normalize_key(room_type: Optional[str]) -> str:
    return (room_type or DEFAULT_ROOM_TYPE).strip().lower().replace(" ", "_").replace("-", "_")


def preset_key_for(room_type: Optional[str]) -> Optional[str]:
    """The preset a room_type string maps to, or None if it is not a known type."""
    key = _normalize_key(room_type)
    key = _ALIASES.get(key, key)
    return key if key in ROOM_TYPE_PRESETS else None


def _preset_for(room_type: Optional[str]) -> RoomTypePreset:
    return ROOM_TYPE_PRESETS[preset_key_for(room_type) or DEFAULT_ROOM_TYPE]


def suggest_ac_count(room_type: Optional[str], capacity: int) -> int:
    """A reasonable default AC count for a room type and capacity — always editable by the
    caller. Rounds UP: you cannot install 4.3 units, and rounding down would size the room
    short on a hot day. The dashboard does the same sum in JavaScript, so the number it
    shows is the number simulated (the 1e-9 guards a float like 3.0000000001)."""
    preset = _preset_for(room_type)
    return max(1, math.ceil(capacity / preset.seats_per_ac_unit - 1e-9))


def _preset_summary(p: RoomTypePreset) -> Dict[str, Any]:
    return {
        "key": p.key,
        "label": p.label,
        "capacity_options": p.capacity_options,
        "default_capacity": p.default_capacity,
        "suggested_ac_count": suggest_ac_count(p.key, p.default_capacity),
        "seats_per_ac_unit": p.seats_per_ac_unit,
        "ac_unit_cooling_kw": AC_UNIT_COOLING_KW,
        "equipment_kw_per_seat": p.equipment_kw_per_seat,
        "notes": p.notes,
    }


def list_room_type_presets() -> List[Dict[str, Any]]:
    """Serializable preset catalogue (no rooms attached)."""
    return [_preset_summary(p) for p in ROOM_TYPE_PRESETS.values()]


def build_venue_catalogue(rooms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every venue type with the listed rooms of that type attached, in dropdown order.

    A room whose room_type matches no preset still appears — under its own type label,
    simulated with the lecture-hall physics — rather than silently vanishing from the list.
    """
    catalogue: Dict[str, Dict[str, Any]] = {key: {**_preset_summary(p), "rooms": []} for key, p in ROOM_TYPE_PRESETS.items()}
    for room in sorted(rooms, key=lambda r: str(r.get("room_id", ""))):
        raw_type = room.get("room_type") or ""
        key = preset_key_for(raw_type) or _normalize_key(raw_type)
        if key not in catalogue:
            catalogue[key] = {**_preset_summary(ROOM_TYPE_PRESETS[DEFAULT_ROOM_TYPE]), "key": key, "label": raw_type, "rooms": []}
        capacity = int(room.get("max_capacity") or catalogue[key]["default_capacity"])
        catalogue[key]["rooms"].append({
            "room_id": room.get("room_id"),
            "building_name": room.get("building_name"),
            "capacity": capacity,
            "suggested_ac_count": suggest_ac_count(key, capacity),
        })
    return list(catalogue.values())


def resolve_room_config(
    room_type: Optional[str],
    capacity: Optional[int] = None,
    num_acs: Optional[int] = None,
) -> ResolvedRoomConfig:
    """Turns (room_type, capacity, num_acs) into concrete 2R2C constants, a fixed
    equipment load and an HVAC cooling ceiling. An unrecognised room type falls back to
    the lecture hall preset rather than raising — this shapes an exploratory simulation,
    not a safety-critical decision, so an unusual label should not hard-fail the tool.
    """
    preset = _preset_for(room_type)

    seats = max(1, int(capacity)) if capacity else preset.default_capacity
    resolved_num_acs = max(1, int(num_acs)) if num_acs else suggest_ac_count(preset.key, seats)

    return ResolvedRoomConfig(
        room_type=preset.key,
        label=preset.label,
        capacity=seats,
        num_acs=resolved_num_acs,
        ac_unit_cooling_kw=AC_UNIT_COOLING_KW,
        total_hvac_capacity_kw=round(resolved_num_acs * AC_UNIT_COOLING_KW, 2),
        equipment_heat_kw=round(preset.equipment_kw_per_seat * seats, 3),
        solar_aperture_m2=round(preset.solar_aperture_m2_per_seat * seats, 3),
        c_in=round(preset.c_in_per_seat * seats, 4),
        r_vent=round(1.0 / (preset.g_vent_per_seat * seats), 5),
        c_wall=round(preset.c_wall_per_seat * seats, 4),
        r_in=round(1.0 / (preset.g_in_per_seat * seats), 5),
        r_out=round(1.0 / (preset.g_out_per_seat * seats), 5),
    )
