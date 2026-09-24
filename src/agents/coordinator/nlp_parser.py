"""
CampusGrid AI: NLP Query Parser & Entity Extractor
Extracts structured parameters and action intent from natural-language facility manager queries:
action, date, building, room, target_temp_c, perturb_temp_delta_c, perturb_occ_multiplier.

Entity extraction is deterministic (rules + the room inventory), so a physical value can never
come from a language model. Every assumption the parser makes (default room, default date,
clamped setpoint) is reported in `notes`, so the dashboard can show the operator what was assumed.
"""

import re
from datetime import date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from src.shared.constants import COMFORT_TEMP_MIN_C, COMFORT_TEMP_MAX_C, COMFORT_SETPOINT_DEFAULT_C
from src.shared.security_patterns import detect_prompt_injection

ACTION_OPTIMIZE_DISPATCH = "optimize_dispatch"
ACTION_WHAT_IF_SIMULATION = "what_if_simulation"
ACTION_POLICY_LOOKUP = "policy_lookup"
ACTION_TELEMETRY_STATUS = "telemetry_status"
ACTION_OUT_OF_SCOPE = "out_of_scope"

ROUTABLE_ACTIONS = [
    ACTION_OPTIMIZE_DISPATCH,
    ACTION_WHAT_IF_SIMULATION,
    ACTION_POLICY_LOOKUP,
    ACTION_TELEMETRY_STATUS,
    ACTION_OUT_OF_SCOPE,
]

# Setpoints outside this band are not plausible requests at all and are ignored, not clamped.
PLAUSIBLE_SETPOINT_RANGE_C = (18.0, 30.0)

_WHAT_IF_WORDS = ["what if", "what-if", "simulate", "simulation", "heatwave", "heat wave", "perturb",
                  "comfort check", "temperature rise", "crowd surge", "solar dropout"]
_POLICY_WORDS = ["tariff", "clause", "rate", "pucsl", "ashrae", "rule", "regulation", "penalty fee",
                 "surcharge", "standard", "net metering"]
_ACTION_WORDS = ["optimize", "optimise", "schedule", "dispatch", "battery", "precool", "pre-cool",
                 "shave", "cut", "reduce", "minimize", "minimise", "plan"]
_TELEMETRY_WORDS = ["forecast", "predict", "prediction", "expected load", "expected demand",
                    "solar generation", "show solar", "telemetry", "demand profile", "load profile"]
_DOMAIN_WORDS = _WHAT_IF_WORDS + _POLICY_WORDS + _ACTION_WORDS + _TELEMETRY_WORDS + [
    "energy", "electricity", "power", "peak", "demand", "load", "solar", "kw", "kwh", "kva", "hvac",
    "chiller", "cooling", "temperature", "comfort", "microgrid", "grid", "soc", "charge", "cost", "bill",
    "saving", "lecture hall", "auditorium", "lab", "room", "building",
]

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# Seed inventory used when no room repository is injected (mirrors InMemoryRoomRepository).
_DEFAULT_ROOMS = {
    "LH-1": {"room_id": "LH-1", "building_name": "Main Academic Complex", "room_type": "Lecture Hall"},
    "AUD-1": {"room_id": "AUD-1", "building_name": "Auditorium Wing", "room_type": "Auditorium"},
    "LAB-3": {"room_id": "LAB-3", "building_name": "Computing Building", "room_type": "Computer Lab"},
}
_EXTRA_ALIASES = {
    "AUD-1": ["auditorium", "main auditorium"],
    "LAB-3": ["computing lab", "computer lab", "lab 3", "lab-3"],
}


def _contains_any(text: str, words: List[str]) -> bool:
    return any(re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", text) for w in words)


class NLPQueryParser:
    """Deterministic entity extractor and rule-based intent classifier for operator queries."""

    def __init__(
        self,
        rooms: Optional[List[Dict[str, Any]]] = None,
        comfort_min_c: float = COMFORT_TEMP_MIN_C,
        comfort_max_c: float = COMFORT_TEMP_MAX_C,
        default_room_id: str = "LH-1",
        reference_date: Optional[date] = None,
    ):
        room_list = rooms or list(_DEFAULT_ROOMS.values())
        self.rooms: Dict[str, Dict[str, Any]] = {r["room_id"].upper(): r for r in room_list}
        self.comfort_min_c = comfort_min_c
        self.comfort_max_c = comfort_max_c
        self.default_room_id = default_room_id if default_room_id.upper() in self.rooms else next(iter(self.rooms))
        self._reference_date = reference_date
        self._aliases = self._build_aliases()

    # ------------------------------------------------------------------

    def parse(self, query: str) -> Dict[str, Any]:
        query_lower = query.lower()
        notes: List[str] = []

        action, confidence = self.classify_intent(query_lower)
        room, building, room_explicit = self._extract_room(query, query_lower, notes)
        target_temp, delta_temp = self._extract_temperatures(query_lower, notes)
        occ_multiplier = self._extract_occupancy(query_lower)
        date_val, date_explicit = self._extract_date(query, query_lower, notes)

        return {
            "action": action,
            "confidence": confidence,
            "intent_source": "rules",
            "building": building,
            "room": room,
            "room_explicit": room_explicit,
            "date": date_val,
            "date_explicit": date_explicit,
            "target_temp_c": target_temp,
            "perturb_temp_delta_c": delta_temp,
            "perturb_occ_multiplier": occ_multiplier,
            "security_flags": detect_prompt_injection(query),
            "notes": notes,
            "raw_query": query
        }

    def classify_intent(self, query_lower: str) -> Tuple[str, float]:
        """Rule-based intent. Low confidence (< 0.6) means an LLM router may refine it."""
        has_action_words = _contains_any(query_lower, _ACTION_WORDS)
        if _contains_any(query_lower, _WHAT_IF_WORDS):
            return ACTION_WHAT_IF_SIMULATION, 0.95
        if _contains_any(query_lower, _POLICY_WORDS) and not has_action_words:
            return ACTION_POLICY_LOOKUP, 0.95
        if _contains_any(query_lower, _TELEMETRY_WORDS) and not has_action_words:
            return ACTION_TELEMETRY_STATUS, 0.90
        if has_action_words:
            return ACTION_OPTIMIZE_DISPATCH, 0.85
        if _contains_any(query_lower, _DOMAIN_WORDS):
            return ACTION_OPTIMIZE_DISPATCH, 0.55
        return ACTION_OUT_OF_SCOPE, 0.40

    # ------------------------------------------------------------------

    def _build_aliases(self) -> List[Tuple[str, str]]:
        aliases: List[Tuple[str, str]] = []
        for room_id, info in self.rooms.items():
            aliases.append((room_id.lower(), room_id))
            aliases.append((room_id.lower().replace("-", ""), room_id))
            aliases.append((room_id.lower().replace("-", " "), room_id))
            number = re.search(r"(\d+)$", room_id)
            room_type = (info.get("room_type") or "").lower()
            if number and room_type:
                aliases.append((f"{room_type} {number.group(1)}", room_id))
            for alias in _EXTRA_ALIASES.get(room_id, []):
                aliases.append((alias, room_id))
        # Longest alias first so "lecture hall 12" can never match as "lecture hall 1".
        return sorted(aliases, key=lambda a: len(a[0]), reverse=True)

    def _extract_room(self, query: str, query_lower: str, notes: List[str]) -> Tuple[str, str, bool]:
        for alias, room_id in self._aliases:
            if re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", query_lower):
                return room_id, self.rooms[room_id].get("building_name", "Main Academic Complex"), True

        # Tariff schedule codes (GP-2, ...) share the room-code shape but are not rooms.
        unknown = next(
            (m for m in re.finditer(r"\b([A-Z]{2,4}-\d{1,3})\b", query) if not m.group(1).startswith("GP-")),
            None,
        )
        if unknown:
            notes.append(f"Room '{unknown.group(1)}' is not in the campus inventory; using {self.default_room_id}.")
        room_id = self.default_room_id
        return room_id, self.rooms[room_id].get("building_name", "Main Academic Complex"), False

    def _extract_temperatures(self, query_lower: str, notes: List[str]) -> Tuple[float, float]:
        temp_pattern = r"(-?\d+(?:\.\d+)?)\s*(?:°\s*c\b|degrees?(?:\s+c(?:elsius)?)?\b|c\b)"
        delta_temp = 0.0
        target_temp = COMFORT_SETPOINT_DEFAULT_C
        target_found = False

        for match in re.finditer(temp_pattern, query_lower):
            value = float(match.group(1))
            prefix = query_lower[max(0, match.start() - 12):match.start()]
            if re.search(r"(?:\+|\bplus\s*|\brise\s+of\s*|\bby\s*|\bincrease\s+of\s*)$", prefix):
                delta_temp = max(-10.0, min(15.0, value))
                continue
            if target_found:
                continue
            target_found = True
            low, high = PLAUSIBLE_SETPOINT_RANGE_C
            if not (low <= value <= high):
                notes.append(f"Ignored implausible setpoint {value:g}°C; using {COMFORT_SETPOINT_DEFAULT_C}°C.")
            elif value < self.comfort_min_c:
                target_temp = self.comfort_min_c
                notes.append(f"Requested {value:g}°C is below the ASHRAE-55 minimum; clamped to {self.comfort_min_c}°C.")
            elif value > self.comfort_max_c:
                target_temp = self.comfort_max_c
                notes.append(f"Requested {value:g}°C is above the ASHRAE-55 maximum; clamped to {self.comfort_max_c}°C.")
            else:
                target_temp = value

        if delta_temp == 0.0 and re.search(r"heat\s?wave", query_lower):
            delta_temp = 3.0
            notes.append("Heatwave with no size given; assumed +3°C ambient.")
        return target_temp, delta_temp

    @staticmethod
    def _extract_occupancy(query_lower: str) -> float:
        percent = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:more|higher|extra)\s+(?:students|occupancy|people|crowd)", query_lower)
        if percent:
            return max(0.0, min(5.0, 1.0 + float(percent.group(1)) / 100.0))
        if "double occupancy" in query_lower or re.search(r"\b2x\b", query_lower):
            return 2.0
        if "triple occupancy" in query_lower or re.search(r"\b3x\b", query_lower):
            return 3.0
        if "half occupancy" in query_lower or re.search(r"\b0\.5x\b", query_lower):
            return 0.5
        if "crowd surge" in query_lower:
            return 2.5
        return 1.0

    def _extract_date(self, query: str, query_lower: str, notes: List[str]) -> Tuple[str, bool]:
        today = self._reference_date or date.today()
        iso = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", query)
        if iso:
            try:
                return date.fromisoformat(iso.group(1)).isoformat(), True
            except ValueError:
                notes.append(f"'{iso.group(1)}' is not a valid date; planning for tomorrow.")
        if "day after tomorrow" in query_lower:
            return (today + timedelta(days=2)).isoformat(), True
        if "tomorrow" in query_lower:
            return (today + timedelta(days=1)).isoformat(), True
        if "today" in query_lower or "tonight" in query_lower:
            return today.isoformat(), True
        for idx, name in enumerate(_WEEKDAYS):
            if re.search(r"\b" + name + r"\b", query_lower):
                days_ahead = (idx - today.weekday()) % 7 or 7
                return (today + timedelta(days=days_ahead)).isoformat(), True
        # Day-ahead planning is the default horizon.
        return (today + timedelta(days=1)).isoformat(), False
