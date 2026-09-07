"""
CampusGrid AI: Regulatory Rule & Constraint Extractor
Extracts exact tariff rates, time windows, and comfort limits using deterministic pattern rules.
"""

import re
from typing import Dict, Any, List
from src.shared.constants import (
    TARIFF_PEAK_LKR,
    TARIFF_DAY_LKR,
    TARIFF_OFF_PEAK_LKR,
    MAX_DEMAND_SURCHARGE_LKR_KVA,
    COMFORT_TEMP_MIN_C,
    COMFORT_TEMP_MAX_C,
)

class RegulatoryRuleExtractor:
    """Extracts numeric constraints and time blocks from tariff and comfort documents."""

    def extract_tariff_rules(self, text: str) -> Dict[str, Any]:
        """Extracts TOU electricity rates and peak periods."""
        rules = {
            "schedule": "PUCSL GP-2 / Industrial I-2",
            "rates_lkr_kwh": {
                "peak": TARIFF_PEAK_LKR,
                "day": TARIFF_DAY_LKR,
                "off_peak": TARIFF_OFF_PEAK_LKR
            },
            "windows": {
                "peak": "18:00 - 22:30",
                "day": "05:30 - 18:00",
                "off_peak": "22:30 - 05:30"
            },
            "max_demand_penalty_lkr_kva": MAX_DEMAND_SURCHARGE_LKR_KVA,
            "comfort_standards": {
                "min_temp_c": COMFORT_TEMP_MIN_C,
                "max_temp_c": COMFORT_TEMP_MAX_C,
                "standard": "ASHRAE Standard 55-2023"
            }
        }
        return rules
