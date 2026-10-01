"""
Timetable upload/editing, the Timetable Coordinator and Works Engineer roles, and the
execution report that closes the loop after a plan is approved.
"""

import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.api.middleware.auth import create_access_token, ROLE_TIMETABLE_COORDINATOR, ROLE_WORKS_ENGINEER
from src.application.services.timetable_service import parse_day, normalise_time

HEADER = "room_id,course_code,day,start_time,end_time,expected_students"


@pytest.fixture(scope="module")
def coordinator_client(test_container):
    return TestClient(app, headers={"Authorization": f"Bearer {create_access_token('timetable', ROLE_TIMETABLE_COORDINATOR)}"})


@pytest.fixture(scope="module")
def works_client(test_container):
    return TestClient(app, headers={"Authorization": f"Bearer {create_access_token('works', ROLE_WORKS_ENGINEER)}"})


@pytest.fixture
def restore_timetable(test_container):
    before = [{k: v for k, v in e.items() if k != "schedule_id"} for e in test_container.timetable_repo.list_all()]
    yield
    test_container.timetable_repo.replace_all(before)


def _upload(client, lines, mode="replace", dry_run=True):
    return client.post("/api/timetable/upload", json={"csv_lines": lines, "mode": mode, "dry_run": dry_run})


# --------------------------------------------------------------------------- parsing

@pytest.mark.parametrize("value,expected", [("Mon", 1), ("monday", 1), ("7", 7), ("SUN", 7), ("8", None), ("Mo", None), ("", None)])
def test_day_parsing(value, expected):
    assert parse_day(value) == expected


def test_time_normalisation():
    assert normalise_time("8:30") == "08:30"
    assert normalise_time("24:00") is None
    assert normalise_time("0830") is None


# --------------------------------------------------------------------------- roles

def test_coordinator_is_limited_to_the_timetable(coordinator_client):
    assert coordinator_client.get("/api/timetable").status_code == 200
    assert coordinator_client.get("/api/audit/logs").status_code == 403
    assert coordinator_client.post("/api/rag/search", json={"query": "peak rate"}).status_code == 403
    assert coordinator_client.post("/api/optimizer/dispatch", json={}).status_code == 403


def test_works_engineer_reads_plans_but_cannot_plan_or_approve(works_client):
    assert works_client.get("/api/audit/logs").status_code == 200
    assert works_client.get("/api/telemetry/forecast").status_code == 200
    assert works_client.post("/api/optimizer/dispatch", json={}).status_code == 403
    assert works_client.post("/api/audit/approve", json={"log_id": 1, "approved": True}).status_code == 403
    assert _upload(works_client, [HEADER, "LH-1,A1,Mon,08:00,09:00,10"]).status_code == 403


def test_operator_and_auditor_cannot_change_the_timetable(operator_client, auditor_client):
    for c in (operator_client, auditor_client):
        assert c.get("/api/timetable").status_code == 200
        assert _upload(c, [HEADER, "LH-1,A1,Mon,08:00,09:00,10"]).status_code == 403


def test_login_returns_the_new_roles(anon_client):
    for username, password, perm in (("timetable", "timetable123", "timetable:manage"), ("works", "works123", "execution:report")):
        data = anon_client.post("/api/auth/login", json={"username": username, "password": password}).json()["data"]
        assert perm in data["permissions"]


# --------------------------------------------------------------------------- upload

def test_dry_run_reports_every_row_error_and_writes_nothing(coordinator_client, test_container, restore_timetable):
    before = test_container.timetable_repo.list_all()
    res = _upload(coordinator_client, [
        HEADER,
        "LH-1,IT3041,Mon,08:30,11:30,220",
        "LH-1,IT3050,Monday,11:00,12:00,100",   # overlaps the row above
        "LH-2,IT2020,Tue,09:00,10:00,999",      # over LH-2's 150 seats
        "ZZ-9,AB12,Wed,10:00,09:00,5",          # unknown room, end before start
    ])
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["applied"] is False and data["valid_rows"] == 2
    messages = " | ".join(e["message"] for e in data["errors"])
    assert "overlaps" in messages and "capacity" in messages and "not in the campus room inventory" in messages
    assert "End time must be after" in messages
    assert test_container.timetable_repo.list_all() == before


def test_apply_is_all_or_nothing(coordinator_client, test_container, restore_timetable):
    before = test_container.timetable_repo.list_all()
    res = _upload(coordinator_client, [HEADER, "LH-1,IT3041,Mon,08:30,11:30,220", "LH-1,BAD,Xday,08:30,11:30,1"], dry_run=False)
    assert res.status_code == 422
    assert res.json()["error_code"] == "TIMETABLE_INVALID"
    assert test_container.timetable_repo.list_all() == before


def test_replace_upload_is_applied_and_audited(coordinator_client, client, test_container, restore_timetable):
    lines = ["﻿" + HEADER, "LH-1,IT3041,Tue,08:30,11:30,220", "", "LH-2,IT2010,2,13:00,15:00,120"]
    data = _upload(coordinator_client, lines, dry_run=False).json()["data"]
    assert data["applied"] is True and data["valid_rows"] == 2
    assert data["sessions_by_day"]["Tue"] == 2
    entries = test_container.timetable_repo.list_all()
    assert {(e["room_id"], e["day_of_week"]) for e in entries} == {("LH-1", 2), ("LH-2", 2)}
    # A weekday with no uploaded sessions is empty, not refilled from the seed Monday.
    assert test_container.timetable_repo.get_schedule_for_day(1) == []
    record = client.get(f"/api/audit/logs/{data['audit_log_id']}").json()["data"]
    assert record["record_type"] == "timetable_update"
    assert record["final_decision"]["sha256"] == data["sha256"]


def test_missing_header_column_is_rejected(coordinator_client):
    res = _upload(coordinator_client, ["room_id,course_code,day,start_time,end_time", "LH-1,A,Mon,08:00,09:00"])
    assert res.status_code == 422
    assert "expected_students" in res.json()["details"]["errors"][0]["message"]


def test_single_session_add_checks_overlap_then_delete(coordinator_client, test_container, restore_timetable):
    _upload(coordinator_client, [HEADER, "LH-1,IT3041,Tue,08:30,11:30,220"], dry_run=False)
    clash = coordinator_client.post("/api/timetable/sessions", json={
        "room_id": "LH-1", "course_code": "MAKEUP", "day": "Tue", "start_time": "10:00", "end_time": "12:00", "expected_students": 50,
    })
    assert clash.status_code == 422 and "overlaps" in clash.json()["details"]["errors"][0]["message"]

    added = coordinator_client.post("/api/timetable/sessions", json={
        "room_id": "LH-1", "course_code": "MAKEUP", "day": "Tue", "start_time": "11:30", "end_time": "12:30", "expected_students": 50,
    })
    assert added.status_code == 200
    schedule_id = added.json()["data"]["entry"]["schedule_id"]
    assert coordinator_client.delete(f"/api/timetable/sessions/{schedule_id}").status_code == 200
    assert coordinator_client.delete(f"/api/timetable/sessions/{schedule_id}").status_code == 404


# --------------------------------------------------------------------------- execution report

def test_execution_report_follows_approval(client, works_client):
    plan = client.post("/api/optimizer/dispatch", json={"date": "2026-10-06"}).json()["data"]
    log_id = plan["audit_log_id"]

    assert works_client.post("/api/audit/execution", json={"log_id": log_id, "outcome": "completed"}).status_code == 409
    assert client.post("/api/audit/approve", json={"log_id": log_id, "approved": True, "acknowledge_warnings": True}).status_code == 200

    partial = works_client.post("/api/audit/execution", json={"log_id": log_id, "outcome": "partial"})
    assert partial.status_code == 422  # must say what was not done
    ok = works_client.post("/api/audit/execution", json={"log_id": log_id, "outcome": "partial", "deviations": "Battery discharge stopped at 20:00."})
    assert ok.status_code == 200
    assert works_client.post("/api/audit/execution", json={"log_id": log_id, "outcome": "completed"}).status_code == 409

    view = works_client.get(f"/api/audit/logs/{log_id}").json()["data"]
    assert view["execution"]["outcome"] == "partial"
    assert view["execution"]["reported_by"] == "works"
    assert client.get("/api/audit/verify").json()["data"]["valid"] is True


def test_direct_forecast_is_audited_with_its_data_sources(client):
    data = client.get("/api/telemetry/forecast", params={"date": "2026-10-06"}).json()["data"]
    assert data["data_sources"]["meter_history"] == "seed_profile"
    assert data["data_quality_notes"]
    record = client.get(f"/api/audit/logs/{data['audit_log_id']}").json()["data"]
    assert record["record_type"] == "forecast_review"
