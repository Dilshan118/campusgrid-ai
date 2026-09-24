"""
CampusGrid AI: Regulatory Rule & Constraint Extractor
Extracts exact tariff rates, time windows, and comfort limits using deterministic pattern rules.

Extraction works sentence by sentence: each sentence is first classified by the tariff
window it talks about (off-peak is checked before peak, so "off-peak" can never be read as
"peak"), then the LKR amount in that sentence is taken. Every extracted number is checked
against a deterministic reference table of plausible values; anything outside it is
rejected and the reference value is used instead, with a warning. This is the defence
against poisoned or prompt-injected policy documents trying to zero out a tariff.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from src.domain.interfaces.policy_extractor import RegulatoryRuleExtractorInterface
from src.shared.constants import (
    TARIFF_PEAK_LKR,
    TARIFF_DAY_LKR,
    TARIFF_OFF_PEAK_LKR,
    MAX_DEMAND_SURCHARGE_LKR_KVA,
    COMFORT_TEMP_MIN_C,
    COMFORT_TEMP_MAX_C,
)

PROVENANCE_RETRIEVED = "retrieved"
PROVENANCE_DEFAULT = "reference_default"
PROVENANCE_REJECTED = "rejected_out_of_range"

# Plausible bounds for a Sri Lankan GP-2 / I-2 tariff. Values outside are treated as corrupt.
PLAUSIBLE_RANGES: Dict[str, Tuple[float, float]] = {
    "peak": (10.0, 200.0),
    "day": (5.0, 150.0),
    "off_peak": (2.0, 100.0),
    "max_demand_penalty_lkr_kva": (100.0, 10_000.0),
    "min_temp_c": (18.0, 24.0),
    "max_temp_c": (23.0, 28.0),
}

REFERENCE_VALUES: Dict[str, float] = {
    "peak": TARIFF_PEAK_LKR,
    "day": TARIFF_DAY_LKR,
    "off_peak": TARIFF_OFF_PEAK_LKR,
    "max_demand_penalty_lkr_kva": MAX_DEMAND_SURCHARGE_LKR_KVA,
    "min_temp_c": COMFORT_TEMP_MIN_C,
    "max_temp_c": COMFORT_TEMP_MAX_C,
}

REFERENCE_WINDOWS: Dict[str, str] = {
    "peak": "18:00 - 22:30",
    "day": "05:30 - 18:00",
    "off_peak": "22:30 - 05:30",
}

_MONEY = r"(\d+(?:\.\d+)?)"
_MONEY_PATTERNS = [
    re.compile(r"\b(?:lkr|rs)\s*" + _MONEY, re.IGNORECASE),   # LKR 58.00 / Rs 58
    re.compile(_MONEY + r"\s*(?:lkr|rs)\b", re.IGNORECASE),   # 58.00 LKR
]
_WINDOW = re.compile(r"\b([01]\d|2[0-3]):([0-5]\d)\s*(?:to|-|–|and|until)\s*([01]\d|2[0-3]):([0-5]\d)")
_COMFORT_ENVELOPE = re.compile(
    r"between\s*(\d+(?:\.\d+)?)\s*°?\s*c\s*and\s*(\d+(?:\.\d+)?)\s*°?\s*c", re.IGNORECASE
)


def _split_sentences(text: str) -> List[str]:
    normalized = re.sub(r"\brs\.", "Rs ", text, flags=re.IGNORECASE).replace(",", "")
    # Split on a period that is not a decimal point, and on line breaks.
    return [s.strip() for s in re.split(r"(?<!\d)\.(?!\d)|\n", normalized) if s.strip()]


def _classify(sentence: str) -> Optional[str]:
    lower = sentence.lower()
    if "kva" in lower and ("demand" in lower or "surcharge" in lower or "penalty" in lower):
        return "max_demand_penalty_lkr_kva"
    if re.search(r"\boff[\s-]?peak\b", lower):
        return "off_peak"
    if re.search(r"\bpeak\b", lower):
        return "peak"
    if re.search(r"\bday[\s-]?time\b|\bdaytime\b|\bday\s+(?:energy|electricity|rate|consumption)\b", lower):
        return "day"
    return None


def _first_amount(sentence: str) -> Optional[float]:
    best: Optional[Tuple[int, float]] = None
    for pattern in _MONEY_PATTERNS:
        m = pattern.search(sentence)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), float(m.group(1)))
    return best[1] if best else None


class RegulatoryRuleExtractor(RegulatoryRuleExtractorInterface):
    """Extracts numeric constraints and time blocks from tariff and comfort documents."""

    def extract_tariff_rules(self, text: str) -> Dict[str, Any]:
        """Extracts TOU electricity rates, demand penalty, and comfort bounds from retrieved text."""
        return self.extract_from_passages([{"content": text, "section_clause": None}])

    def extract_from_passages(self, passages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Like extract_tariff_rules, but records which retrieved clause each figure came from.

        `passages` are citation dicts with at least 'content' and optionally 'section_clause'
        and 'document_title'. Earlier passages (higher-ranked) win when two clauses disagree.
        """
        found: Dict[str, float] = {}
        sources: Dict[str, Optional[str]] = {}
        windows: Dict[str, str] = {}

        for passage in passages:
            content = passage.get("content") or ""
            source = passage.get("section_clause")
            if source and passage.get("document_title"):
                source = f"{passage['document_title']} — {source}"

            for sentence in _split_sentences(content):
                field = _classify(sentence)
                if field is None:
                    continue
                amount = _first_amount(sentence)
                if amount is not None and field not in found:
                    found[field] = amount
                    sources[field] = source
                window = _WINDOW.search(sentence)
                if window and field in REFERENCE_WINDOWS and field not in windows:
                    windows[field] = f"{window.group(1)}:{window.group(2)} - {window.group(3)}:{window.group(4)}"

            envelope = _COMFORT_ENVELOPE.search(content.replace(",", ""))
            if envelope and "min_temp_c" not in found:
                found["min_temp_c"] = float(envelope.group(1))
                found["max_temp_c"] = float(envelope.group(2))
                sources["min_temp_c"] = sources["max_temp_c"] = source

        values, provenance, warnings = self._validate(found)
        for key in list(sources):
            if provenance.get(key) != PROVENANCE_RETRIEVED:
                sources[key] = None

        return {
            "schedule": "PUCSL GP-2 / Industrial I-2",
            "rates_lkr_kwh": {
                "peak": values["peak"],
                "day": values["day"],
                "off_peak": values["off_peak"]
            },
            "windows": {k: windows.get(k, v) for k, v in REFERENCE_WINDOWS.items()},
            "max_demand_penalty_lkr_kva": values["max_demand_penalty_lkr_kva"],
            "comfort_standards": {
                "min_temp_c": values["min_temp_c"],
                "max_temp_c": values["max_temp_c"],
                "standard": "ASHRAE Standard 55-2023"
            },
            "provenance": provenance,
            "source_clauses": {k: v for k, v in sources.items() if v},
            "validation_warnings": warnings,
            "all_rates_retrieved": all(provenance[k] == PROVENANCE_RETRIEVED for k in ("peak", "day", "off_peak")),
        }

    @staticmethod
    def _validate(found: Dict[str, float]) -> Tuple[Dict[str, float], Dict[str, str], List[str]]:
        values: Dict[str, float] = {}
        provenance: Dict[str, str] = {}
        warnings: List[str] = []

        for key, reference in REFERENCE_VALUES.items():
            if key not in found:
                values[key], provenance[key] = reference, PROVENANCE_DEFAULT
                continue
            low, high = PLAUSIBLE_RANGES[key]
            if low <= found[key] <= high:
                values[key], provenance[key] = found[key], PROVENANCE_RETRIEVED
            else:
                values[key], provenance[key] = reference, PROVENANCE_REJECTED
                warnings.append(
                    f"Retrieved {key}={found[key]} is outside the plausible range [{low}, {high}]; "
                    f"using reference value {reference}."
                )

        # Tariff ordering must hold: off-peak <= day <= peak. A violation means the retrieved
        # figures are inconsistent, so all three revert to the reference schedule.
        if not (values["off_peak"] <= values["day"] <= values["peak"]):
            warnings.append(
                f"Retrieved rates violate off-peak <= day <= peak ({values['off_peak']}, {values['day']}, "
                f"{values['peak']}); using the reference tariff schedule."
            )
            for key in ("peak", "day", "off_peak"):
                if provenance[key] == PROVENANCE_RETRIEVED:
                    provenance[key] = PROVENANCE_REJECTED
                values[key] = REFERENCE_VALUES[key]

        if values["min_temp_c"] >= values["max_temp_c"]:
            warnings.append("Retrieved comfort envelope is inverted; using the ASHRAE-55 reference band.")
            for key in ("min_temp_c", "max_temp_c"):
                provenance[key] = PROVENANCE_REJECTED
                values[key] = REFERENCE_VALUES[key]

        return values, provenance, warnings
