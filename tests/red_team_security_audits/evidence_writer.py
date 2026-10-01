"""Optional JSON evidence capture for individual red-team case records."""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def capture_case(case: Dict[str, Any]) -> None:
    """Persist measured case fields when CAMPUSGRID_WRITE_AUDIT_EVIDENCE=1."""
    if os.environ.get("CAMPUSGRID_WRITE_AUDIT_EVIDENCE") != "1":
        return
    match = re.fullmatch(r"TC-S([1-4])-([0-9]{2})", str(case.get("test_id", "")))
    if not match:
        raise ValueError(f"Invalid security audit case id: {case.get('test_id')!r}")
    root = Path(__file__).resolve().parent / "evidence" / f"student{match.group(1)}" / "cases"
    root.mkdir(parents=True, exist_ok=True)
    record = dict(case)
    record["evidence_generated_utc"] = datetime.now(timezone.utc).isoformat()
    record["test_source"] = f"tests/red_team_security_audits/test_student{match.group(1)}_*.py"
    record["python_version"] = sys.version.split()[0]
    record["embedding_provider"] = os.environ.get("EMBEDDING_PROVIDER", "configured-default")
    record["llm_provider"] = os.environ.get("LLM_PROVIDER", "configured-default")
    (root / f"TC-S{match.group(1)}-{match.group(2)}.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
