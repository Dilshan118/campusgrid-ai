"""
CampusGrid AI: Timetable Service
Validates and applies timetable changes: a whole-semester CSV upload or a single session added
through the dashboard form. There is no live timetable feed; this is how the faculty timetable
office keeps CampusGrid's expected occupancy current.

CSV format (one row per weekly teaching session, header required, extra columns ignored):

    room_id,course_code,day,start_time,end_time,expected_students
    LH-1,IT3041,Mon,08:30,11:30,220

`day` accepts Mon..Sun, Monday..Sunday or 1..7 (1 = Monday). Times are 24-hour HH:MM.
Every row is validated before anything is written, so an upload applies completely or not at
all, and each applied change is appended to the audit trail with the file's SHA-256.
"""

import csv
import hashlib
import io
import re
import threading
from typing import Any, Dict, List, Optional, Tuple
from src.domain.interfaces.repositories import TimetableRepository, RoomRepository
from src.domain.entities.audit import RECORD_TIMETABLE_UPDATE
from src.domain.exceptions.base import DomainException, EntityNotFoundError
from src.application.services.audit_service import AuditService

REQUIRED_COLUMNS = ("room_id", "course_code", "day", "start_time", "end_time", "expected_students")
MAX_ROWS = 5000
MODE_REPLACE = "replace"
MODE_APPEND = "append"

_DAY_NAMES = {name: i + 1 for i, name in enumerate(("mon", "tue", "wed", "thu", "fri", "sat", "sun"))}
_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_COURSE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _./()-]{0,49}$")
_FULL_DAY_NAMES = {name: i + 1 for i, name in enumerate(
    ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"))}
DAY_LABELS = {v: k.title() for k, v in _DAY_NAMES.items()}


class TimetableValidationError(DomainException):
    def __init__(self, errors: List[Dict[str, Any]], message: str = "The timetable has errors; nothing was changed."):
        super().__init__(message=message, error_code="TIMETABLE_INVALID", details={"status": 422, "errors": errors[:200]})


def parse_day(value: Any) -> Optional[int]:
    text = str(value or "").strip().lower()
    if text.isdigit():
        return int(text) if 1 <= int(text) <= 7 else None
    return _DAY_NAMES.get(text) or _FULL_DAY_NAMES.get(text)


def normalise_time(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if re.match(r"^\d:\d\d$", text):  # "8:30" from spreadsheets
        text = "0" + text
    return text if _TIME.match(text) else None


class TimetableService:
    def __init__(self, timetable_repo: TimetableRepository, room_repo: RoomRepository, audit_service: AuditService):
        self.timetable_repo = timetable_repo
        self.room_repo = room_repo
        self.audit_service = audit_service
        self._lock = threading.Lock()  # validate-then-write must not interleave with another change

    # ------------------------------------------------------------------ reads

    def list_entries(self, day_of_week: Optional[int] = None) -> Dict[str, Any]:
        entries = self.timetable_repo.list_all()
        if day_of_week is not None:
            entries = [e for e in entries if e["day_of_week"] == day_of_week]
        return {"entries": entries, "source": self.timetable_repo.source(), "count": len(entries)}

    # ------------------------------------------------------------------ validation

    def _rooms(self) -> Dict[str, Dict[str, Any]]:
        return {str(r["room_id"]).upper(): r for r in self.room_repo.list_all()}

    def _validate_row(self, raw: Dict[str, Any], line: int, rooms: Dict[str, Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        errors: List[Dict[str, Any]] = []

        def err(field: str, message: str):
            errors.append({"line": line, "field": field, "message": message})

        room_id = str(raw.get("room_id") or "").strip().upper()
        room = rooms.get(room_id)
        if not room_id:
            err("room_id", "Room is required.")
        elif room is None:
            err("room_id", f"Room '{room_id}' is not in the campus room inventory.")

        course = str(raw.get("course_code") or "").strip()
        if not _COURSE.match(course):
            err("course_code", "Course code is required: letters, digits, spaces and - _ . / ( ), at most 50 characters.")

        day = parse_day(raw.get("day", raw.get("day_of_week")))
        if day is None:
            err("day", "Day must be Mon-Sun, Monday-Sunday or 1-7 (1 = Monday).")

        start, end = normalise_time(raw.get("start_time")), normalise_time(raw.get("end_time"))
        if start is None:
            err("start_time", "Start time must be 24-hour HH:MM, e.g. 08:30.")
        if end is None:
            err("end_time", "End time must be 24-hour HH:MM, e.g. 11:30.")
        if start and end and start >= end:
            err("end_time", "End time must be after the start time.")

        students_raw = str(raw.get("expected_students") or "").strip()
        students = int(students_raw) if students_raw.isdigit() else None
        if students is None:
            err("expected_students", "Expected students must be a whole number.")
        elif room is not None and students > int(room["max_capacity"]):
            err("expected_students", f"{students} students exceeds {room_id}'s capacity of {room['max_capacity']}.")

        if errors:
            return None, errors
        return {
            "room_id": room_id, "course_code": course, "day_of_week": day,
            "start_time": start, "end_time": end, "expected_students": students,
        }, []

    @staticmethod
    def _overlaps(entries: List[Tuple[int, Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Two sessions in the same room on the same day whose times overlap (touching ends are fine)."""
        errors = []
        by_slot: Dict[Tuple[str, int], List[Tuple[int, Dict[str, Any]]]] = {}
        for line, e in entries:
            by_slot.setdefault((e["room_id"], e["day_of_week"]), []).append((line, e))
        for (room, day), group in by_slot.items():
            group.sort(key=lambda le: le[1]["start_time"])
            for (l1, a), (l2, b) in zip(group, group[1:]):
                if b["start_time"] < a["end_time"]:
                    where = f"line {l1}" if l1 > 0 else f"existing session {a['course_code']}"
                    errors.append({
                        "line": l2, "field": "start_time",
                        "message": f"{b['course_code']} overlaps {a['course_code']} ({where}) in {room} on "
                                   f"{DAY_LABELS[day]} {a['start_time']}-{a['end_time']}.",
                    })
        return errors

    def _validate(self, rows: List[Tuple[int, Dict[str, Any]]], existing: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        rooms = self._rooms()
        valid: List[Tuple[int, Dict[str, Any]]] = []
        errors: List[Dict[str, Any]] = []
        for line, raw in rows:
            entry, row_errors = self._validate_row(raw, line, rooms)
            errors.extend(row_errors)
            if entry:
                valid.append((line, entry))
        # Existing sessions carry line 0 so an overlap names them rather than a CSV line.
        errors.extend(self._overlaps([(0, e) for e in existing] + valid))
        return [e for _, e in valid], sorted(errors, key=lambda e: e["line"])

    # ------------------------------------------------------------------ CSV upload

    @staticmethod
    def parse_csv(csv_text: str) -> List[Tuple[int, Dict[str, Any]]]:
        text = csv_text.lstrip("\ufeff")  # Excel's "CSV UTF-8" adds a byte-order mark
        reader = csv.DictReader(io.StringIO(text))
        header = [h.strip().lower() for h in (reader.fieldnames or [])]
        missing = [c for c in REQUIRED_COLUMNS if c not in header and not (c == "day" and "day_of_week" in header)]
        if missing:
            raise TimetableValidationError(
                [{"line": 1, "field": "header", "message": f"Missing column(s): {', '.join(missing)}."}],
                message="The CSV header is missing required columns.",
            )
        rows = []
        for i, row in enumerate(reader, start=2):  # line 1 is the header
            cleaned = {str(k).strip().lower(): (v or "").strip() for k, v in row.items() if k is not None}
            if not any(cleaned.values()):
                continue  # blank line
            rows.append((i, cleaned))
            if len(rows) > MAX_ROWS:
                raise TimetableValidationError(
                    [{"line": i, "field": "file", "message": f"At most {MAX_ROWS} sessions per upload."}],
                    message="The CSV has too many rows.",
                )
        if not rows:
            raise TimetableValidationError([{"line": 2, "field": "file", "message": "The CSV has no sessions."}],
                                           message="The CSV has no sessions.")
        return rows

    def upload_csv(self, csv_text: str, mode: str, user_id: str, dry_run: bool, filename: Optional[str] = None) -> Dict[str, Any]:
        if mode not in (MODE_REPLACE, MODE_APPEND):
            raise DomainException("mode must be 'replace' or 'append'.", "VALIDATION_ERROR", {"status": 422, "field": "mode"})
        rows = self.parse_csv(csv_text)
        digest = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
        with self._lock:
            existing = [] if mode == MODE_REPLACE else self.timetable_repo.list_all()
            entries, errors = self._validate(rows, existing)
            summary = {
                "mode": mode, "rows": len(rows), "valid_rows": len(entries), "errors": errors,
                "sessions_by_day": {DAY_LABELS[d]: sum(1 for e in entries if e["day_of_week"] == d) for d in range(1, 8)},
                "rooms": sorted({e["room_id"] for e in entries}),
                "sha256": digest, "dry_run": dry_run, "applied": False,
            }
            if dry_run:
                return {**summary, "preview": entries[:50]}
            if errors:
                raise TimetableValidationError(errors)
            if mode == MODE_REPLACE:
                self.timetable_repo.replace_all(entries)
            else:
                self.timetable_repo.add_entries(entries)
            summary["applied"] = True
            summary["audit_log_id"] = self._audit(user_id, f"Timetable CSV upload ({mode}): {filename or 'unnamed file'}", {
                "change": f"csv_{mode}", "filename": filename, "rows_applied": len(entries), "sha256": digest,
                "sessions_by_day": summary["sessions_by_day"], "rooms": summary["rooms"],
            })
            return summary

    # ------------------------------------------------------------------ single-session form

    def add_session(self, raw: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        with self._lock:
            entries, errors = self._validate([(1, raw)], self.timetable_repo.list_all())
            if errors:
                raise TimetableValidationError(errors, message="The session has errors; it was not added.")
            entry = entries[0]
            [schedule_id] = self.timetable_repo.add_entries([entry])
            entry = {**entry, "schedule_id": schedule_id}
            log_id = self._audit(user_id, f"Timetable session added: {entry['course_code']} in {entry['room_id']}",
                                 {"change": "session_added", "session": entry})
            return {"entry": entry, "audit_log_id": log_id}

    def delete_session(self, schedule_id: int, user_id: str) -> Dict[str, Any]:
        with self._lock:
            entry = next((e for e in self.timetable_repo.list_all() if e["schedule_id"] == schedule_id), None)
            if entry is None or not self.timetable_repo.delete_entry(schedule_id):
                raise EntityNotFoundError(entity_type="TimetableSession", identifier=schedule_id)
            log_id = self._audit(user_id, f"Timetable session removed: {entry['course_code']} in {entry['room_id']}",
                                 {"change": "session_removed", "session": entry})
            return {"deleted": schedule_id, "audit_log_id": log_id}

    def _audit(self, user_id: str, query: str, decision: Dict[str, Any]) -> int:
        return self.audit_service.log_operator_action(
            user_id=user_id, query=query, agent_sequence={}, decision=decision, record_type=RECORD_TIMETABLE_UPDATE,
        )
