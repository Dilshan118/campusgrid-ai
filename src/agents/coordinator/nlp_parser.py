"""
CampusGrid AI: NLP Query Parser & Entity Extractor
Extracts structured parameters from operator natural-language queries:
action, date, building, room, target_temp_c.
"""

import re
from typing import Dict, Any, Optional

class NLPQueryParser:
    """Deterministic and LLM-assisted query parser."""

    def parse(self, query: str) -> Dict[str, Any]:
        query_lower = query.lower()

        # Action identification
        action = "optimize_dispatch"
        if "what if" in query_lower or "simulate" in query_lower or "heatwave" in query_lower:
            action = "what_if_simulation"
        elif "tariff" in query_lower or "clause" in query_lower or "rate" in query_lower or "pucsl" in query_lower:
            action = "policy_lookup"

        # Room identification
        room = "LH-1"
        if "auditorium" in query_lower:
            room = "AUD-1"
        elif "lab" in query_lower:
            room = "LAB-3"
        elif "lh-1" in query_lower or "lecture hall 1" in query_lower:
            room = "LH-1"

        # Building identification
        building = "Main Academic Complex"
        if "auditorium" in query_lower:
            building = "Auditorium Wing"
        elif "computing" in query_lower or "lab" in query_lower:
            building = "Computing Building"

        # Temperature extraction (e.g. "23.5 degrees", "precool to 22C")
        target_temp = 24.0
        temp_match = re.search(r"(\d{2}(?:\.\d)?)\s*(?:°?c|degrees)", query_lower)
        if temp_match:
            target_temp = float(temp_match.group(1))

        # Date extraction (e.g. 2026-09-06)
        date_match = re.search(r"\b(202\d-\d{2}-\d{2})\b", query)
        date_val = date_match.group(1) if date_match else "2026-09-06"

        return {
            "action": action,
            "building": building,
            "room": room,
            "date": date_val,
            "target_temp_c": target_temp,
            "raw_query": query
        }
