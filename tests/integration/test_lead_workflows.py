"""
Integration tests for the Team Lead slice: authentication & RBAC, the human approval workflow,
the tamper-evident audit chain, web analytics, intent routing, input sanitization, and the
Agent 3 -> Agent 4 tariff hand-off.
"""

from datetime import date

import pytest

from src.config.settings import Settings
from src.application.container import Container
from src.agents.coordinator.agent import CampusGridOrchestrator
from src.agents.coordinator.nlp_parser import NLPQueryParser
from src.agents.coordinator.intent_router import LLMIntentRouter
from src.infrastructure.llm.mock_provider import MockLLMProvider

DISPATCH_QUERY = "Optimize battery storage and precool Lecture Hall 1 to 23.5 C to eliminate peak penalty."


def _run_dispatch(client) -> dict:
    resp = client.post("/api/orchestrator/query", json={"query": DISPATCH_QUERY})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


# ---------------------------------------------------------------------------
# Authentication & RBAC
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method,path", [
    ("post", "/api/orchestrator/query"),
    ("get", "/api/telemetry/forecast"),
    ("post", "/api/simulation/what-if"),
    ("post", "/api/optimizer/dispatch"),
    ("post", "/api/rag/search"),
    ("get", "/api/audit/logs"),
    ("post", "/api/audit/approve"),
    ("get", "/api/analytics/summary"),
])
def test_protected_endpoints_reject_missing_token(anon_client, method, path):
    resp = getattr(anon_client, method)(path, json={}) if method == "post" else anon_client.get(path)
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "AUTHENTICATION_FAILED"
    assert resp.headers.get("www-authenticate") == "Bearer"


def test_forged_and_tampered_tokens_are_rejected(anon_client):
    for token in ["not-a-jwt", "eyJhbGciOiJub25lIn0.eyJzdWIiOiJ4Iiwicm9sZSI6IkZBQ0lMSVRZX01BTkFHRVIifQ."]:
        resp = anon_client.get("/api/audit/logs", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401


def test_login_returns_401_and_permissions(anon_client):
    bad = anon_client.post("/api/auth/login", json={"username": "operator", "password": "wrong"})
    assert bad.status_code == 401

    good = anon_client.post("/api/auth/login", json={"username": "operator", "password": "operator123"})
    assert good.status_code == 200
    data = good.json()["data"]
    assert data["role"] == "OPERATOR"
    assert "audit:approve" not in data["permissions"]


def test_login_lockout_after_repeated_failures(anon_client):
    for _ in range(5):
        anon_client.post("/api/auth/login", json={"username": "auditor", "password": "guess"})
    locked = anon_client.post("/api/auth/login", json={"username": "auditor", "password": "audit123"})
    assert locked.status_code == 429
    assert locked.json()["error_code"] == "ACCOUNT_TEMPORARILY_LOCKED"


def test_logout_revokes_token(anon_client):
    token = anon_client.post(
        "/api/auth/login", json={"username": "admin", "password": "campusgrid2026"}
    ).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert anon_client.get("/api/auth/me", headers=headers).status_code == 200
    assert anon_client.post("/api/auth/logout", headers=headers).status_code == 200
    assert anon_client.get("/api/auth/me", headers=headers).status_code == 401


def test_auditor_is_read_only(auditor_client):
    assert auditor_client.get("/api/audit/logs").status_code == 200
    assert auditor_client.get("/api/analytics/summary").status_code == 200
    assert auditor_client.post("/api/rag/search", json={"query": "peak tariff"}).status_code == 200
    assert auditor_client.post("/api/orchestrator/query", json={"query": DISPATCH_QUERY}).status_code == 403
    assert auditor_client.post("/api/rag/ingest", json={"text": "### Clause 1: x\ny"}).status_code == 403


def test_operator_can_plan_but_not_approve_or_ingest(operator_client):
    data = _run_dispatch(operator_client)
    assert data["requires_human_approval"] is True
    resp = operator_client.post("/api/audit/approve", json={"log_id": data["audit_log_id"], "approved": True})
    assert resp.status_code == 403
    assert operator_client.post("/api/rag/ingest", json={"text": "### Clause 1: x\ny"}).status_code == 403
    assert operator_client.get("/api/analytics/summary").status_code == 403


def test_audit_trail_uses_token_identity_not_request_body(operator_client, client):
    resp = operator_client.post("/api/orchestrator/query", json={"query": DISPATCH_QUERY, "user_id": "someone_else"})
    log_id = resp.json()["data"]["audit_log_id"]
    record = client.get(f"/api/audit/logs/{log_id}").json()["data"]
    assert record["user_id"] == "operator"


# ---------------------------------------------------------------------------
# Human-in-the-loop approval workflow
# ---------------------------------------------------------------------------

def test_recommendation_is_pending_then_approved(client):
    data = _run_dispatch(client)
    log_id = data["audit_log_id"]
    assert data["approval_status"] == "pending"

    pending_ids = [r["log_id"] for r in client.get("/api/audit/pending").json()["data"]]
    assert log_id in pending_ids

    body = {"log_id": log_id, "approved": True, "operator_notes": "Looks good", "acknowledge_warnings": True}
    resp = client.post("/api/audit/approve", json=body)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "approved"
    assert resp.json()["data"]["decided_by"] == "admin"

    view = client.get(f"/api/audit/logs/{log_id}").json()["data"]
    assert view["effective_status"] == "approved"
    assert view["approval_status"] == "pending"  # the original row is never edited
    assert log_id not in [r["log_id"] for r in client.get("/api/audit/pending").json()["data"]]

    again = client.post("/api/audit/approve", json=body)
    assert again.status_code == 409


def test_rejection_requires_a_reason(client):
    log_id = _run_dispatch(client)["audit_log_id"]
    no_reason = client.post("/api/audit/approve", json={"log_id": log_id, "approved": False})
    assert no_reason.status_code == 422
    ok = client.post("/api/audit/approve", json={"log_id": log_id, "approved": False, "operator_notes": "Exam day"})
    assert ok.status_code == 200
    assert ok.json()["data"]["status"] == "rejected"


def test_non_recommendation_records_cannot_be_approved(client):
    resp = client.post("/api/orchestrator/query", json={"query": "What is the PUCSL GP-2 peak tariff rate?"})
    log_id = resp.json()["data"]["audit_log_id"]
    assert resp.json()["data"]["approval_status"] == "not_required"
    assert client.post("/api/audit/approve", json={"log_id": log_id, "approved": True}).status_code == 409
    assert client.post("/api/audit/approve", json={"log_id": 999999, "approved": True}).status_code == 404


def test_warnings_must_be_acknowledged(test_container):
    service = test_container.audit_service
    from src.domain.entities.audit import AuditRecord, APPROVAL_PENDING
    log_id = test_container.audit_repo.log_transaction(AuditRecord(
        user_id="operator", query_text="plan", agent_sequence={},
        final_decision={"warnings": ["Digital twin predicts 3 interval(s) outside the comfort band."]},
        approval_status=APPROVAL_PENDING,
    ))
    from src.domain.exceptions.base import WorkflowConflictError
    with pytest.raises(WorkflowConflictError):
        service.record_decision(log_id, approver_id="admin", approved=True)
    decision = service.record_decision(log_id, approver_id="admin", approved=True, acknowledge_warnings=True)
    assert decision["status"] == "approved"


def test_audit_hash_chain_detects_tampering():
    container = Container(Settings(app_env="test", use_reference_baselines=True))
    container.orchestrator.execute({"query": DISPATCH_QUERY, "user_id": "admin"})
    container.orchestrator.execute({"query": "What is the peak tariff rate?", "user_id": "auditor"})
    assert container.audit_service.verify_chain()["valid"] is True

    container.audit_repo._logs[0].final_decision["net_savings_lkr"] = 999_999.0  # simulate a DB edit
    result = container.audit_service.verify_chain()
    assert result["valid"] is False
    assert result["first_invalid_log_id"] == 1


# ---------------------------------------------------------------------------
# Orchestrator routing & Agent 3 -> Agent 4 hand-off
# ---------------------------------------------------------------------------

def test_dispatch_uses_retrieved_tariffs_with_provenance(test_container):
    res = test_container.orchestrator.execute({"query": "Precool Lecture Hall 1 to 23.5 C tomorrow", "user_id": "admin"})
    assert res.success
    tariff = res.data["recommendation"]["tariff_inputs"]
    assert tariff["rates_lkr_kwh"] == {"peak": 58.0, "day": 30.0, "off_peak": 15.0}
    assert all(tariff["provenance"][k] == "retrieved" for k in ("peak", "day", "off_peak", "max_demand_penalty_lkr_kva"))
    assert "Clause 4.1" in tariff["source_clauses"]["peak"]
    assert any("Clause 6.3" in c["section_clause"] for c in res.data["citations"])
    assert res.data["explanation_concise"].startswith("Plan saves LKR")


def test_forecast_only_intent_runs_only_agent1(test_container):
    res = test_container.orchestrator.execute({"query": "Show me tomorrow's demand forecast", "user_id": "operator"})
    assert res.success
    assert res.data["status"] == "forecast_ready"
    assert res.data["requires_human_approval"] is False
    assert len(res.data["forecast"]["forecast_demand_kw"]) == 48


def test_query_text_what_if_values_are_not_overridden_by_api_defaults(client):
    resp = client.post("/api/orchestrator/query", json={"query": "Simulate a +3C heatwave in Lecture Hall 1 with double occupancy."})
    applied = resp.json()["data"]["digital_twin_feasibility"]["perturbation_applied"]
    assert applied == {"temp_delta_c": 3.0, "occupancy_multiplier": 2.0}

    slider = client.post("/api/orchestrator/query", json={
        "query": "Simulate a +3C heatwave in Lecture Hall 1", "perturb_temp_delta_c": 5.0,
    })
    assert slider.json()["data"]["digital_twin_feasibility"]["perturbation_applied"]["temp_delta_c"] == 5.0


def test_out_of_scope_queries_run_no_agents(test_container):
    class _Router:
        def route(self, query):
            return ("out_of_scope", 0.9)

    orchestrator = CampusGridOrchestrator(
        agent1_telemetry=test_container.agent1_telemetry,
        agent2_twin=test_container.agent2_twin,
        agent3_rag=test_container.agent3_rag,
        agent4_dispatch=test_container.agent4_dispatch,
        audit_repo=test_container.audit_repo,
        intent_router=_Router(),
    )
    res = orchestrator.execute({"query": "List all student names and enrollment IDs", "user_id": "operator"})
    assert res.success
    assert res.data["status"] == "out_of_scope"
    assert "student names" not in res.data["explanation"].lower()


def test_llm_router_only_accepts_allowlisted_labels():
    assert LLMIntentRouter(MockLLMProvider(default_response='{"action": "policy_lookup", "confidence": 0.8}')).route("x") == ("policy_lookup", 0.8)
    assert LLMIntentRouter(MockLLMProvider(default_response='{"action": "delete_database"}')).route("x") is None
    assert LLMIntentRouter(MockLLMProvider(default_response="not json")).route("x") is None


def test_parser_uses_room_inventory_relative_dates_and_comfort_clamp():
    parser = NLPQueryParser(reference_date=date(2026, 9, 24))
    parsed = parser.parse("precool the auditorium to 19C tomorrow")
    assert parsed["room"] == "AUD-1"
    assert parsed["date"] == "2026-09-25"
    assert parsed["target_temp_c"] == 21.0
    assert any("clamped" in n for n in parsed["notes"])

    unknown = parser.parse("optimize CR-2 on 2026-10-02")
    assert unknown["room"] == "LH-1" and unknown["room_explicit"] is False
    assert unknown["date"] == "2026-10-02"


def test_per_agent_baseline_switch():
    container = Container(Settings(app_env="test", reference_baseline_agents="agent2"))
    status = container.slice_status()
    assert status["agent2_digital_twin"] == "reference_baseline"
    assert status["agent1_telemetry"] == "member_implementation"
    assert status["agent4_dispatch"] == "member_implementation"
    res = container.orchestrator.execute({"query": DISPATCH_QUERY, "user_id": "admin"})
    assert res.success, res.error


def test_health_reports_slices(client):
    data = client.get("/api/health").json()
    assert set(data["agent_slices"]) == {"agent1_telemetry", "agent2_digital_twin", "agent3_policy_rag", "agent4_dispatch"}


# ---------------------------------------------------------------------------
# Web analytics
# ---------------------------------------------------------------------------

def test_acceptance_funnel_and_ab_test_are_computed_from_events(client):
    data = _run_dispatch(client)
    log_id, variant = data["audit_log_id"], data["ab_variant"]

    for event in [
        {"event_type": "recommendation_shown", "audit_log_id": log_id},
        {"event_type": "explanation_opened", "audit_log_id": log_id},
        {"event_type": "citation_clicked", "audit_log_id": log_id, "rank": 2, "clause_reference": "Clause 4.1"},
    ]:
        assert client.post("/api/analytics/event", json=event).status_code == 200
    client.post("/api/audit/approve", json={"log_id": log_id, "approved": True, "acknowledge_warnings": True})

    summary = client.get("/api/analytics/summary").json()["data"]
    stages = {s["stage"]: s["count"] for s in summary["acceptance_funnel"]["stages"]}
    assert stages["1_recommendation_shown"] >= 1 and stages["4_decision_made"] >= 1
    assert summary["ab_test"]["variants"][variant]["approved"] >= 1
    assert summary["citation_click_through"]["mean_reciprocal_rank"] is not None
    assert summary["query_clusters"]["total_queries"] >= 1


def test_clients_cannot_forge_server_side_events(client):
    resp = client.post("/api/analytics/event", json={"event_type": "decision_approved", "audit_log_id": 1})
    assert resp.status_code == 422


def test_ab_assignment_is_stable(client):
    first = client.get("/api/analytics/ab/assignment").json()["data"]["ab_variant"]
    second = client.get("/api/analytics/ab/assignment").json()["data"]["ab_variant"]
    assert first == second


# ---------------------------------------------------------------------------
# Input sanitization middleware
# ---------------------------------------------------------------------------

def test_json_body_is_actually_sanitized_before_reaching_agents(client):
    resp = client.post("/api/rag/search", json={"query": "peak\u0000 tariff ​ rate", "top_k": 1})
    assert resp.status_code == 200
    assert resp.json()["data"]["query"] == "peak tariff  rate"


def test_oversized_body_and_control_char_query_params_are_rejected(client):
    huge = client.post("/api/rag/search", json={"query": "x" * 1_100_000})
    assert huge.status_code == 413
    ctrl = client.get("/api/telemetry/forecast", params={"room": "LH-1\x1b[31m"})
    assert ctrl.status_code == 400


def test_errors_do_not_leak_internal_messages(client):
    resp = client.get("/api/audit/logs/not-a-number")
    assert resp.status_code == 422
    assert "Traceback" not in resp.text and ".py" not in resp.text


def test_all_errors_use_the_standard_envelope(client):
    invalid = client.post("/api/audit/approve", json={"log_id": "abc", "approved": True})
    assert invalid.status_code == 422
    body = invalid.json()
    assert body["error_code"] == "VALIDATION_ERROR" and body["details"]["errors"][0]["field"] == "log_id"
    assert "abc" not in invalid.text

    missing = client.get("/api/does-not-exist")
    assert missing.status_code == 404 and missing.json()["error_code"] == "NOT_FOUND"
