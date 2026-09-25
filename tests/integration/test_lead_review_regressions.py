"""
Regression tests for defects found in the September 2026 Lead code review. Each test fails on the
code as it was before its fix: off-topic queries routed to dispatch by the mock LLM, plural keywords
ignored by the intent rules, internal error text returned to clients, two concurrent decisions on
one plan, a missing comfort verdict reported as comfortable, a working-directory-dependent corpus
path, and '+json' bodies skipping input sanitization.
"""

import asyncio
import json
import logging
import threading
import time

import pytest

from src.api.middleware.sanitization import InputSanitizationMiddleware
from src.agents.base.agent import BaseAgent
from src.agents.coordinator.agent import CampusGridOrchestrator
from src.agents.coordinator.intent_router import LLMIntentRouter
from src.agents.coordinator.nlp_parser import (
    NLPQueryParser,
    ACTION_OPTIMIZE_DISPATCH,
    ACTION_POLICY_LOOKUP,
    ACTION_TELEMETRY_STATUS,
)
from src.application.services.audit_service import AuditService
from src.application.services.retrieval_service import RetrievalService, _FALLBACK_CLAUSES
from src.domain.entities.audit import AuditRecord, RECORD_DISPATCH_RECOMMENDATION, RECORD_APPROVAL_DECISION, APPROVAL_PENDING
from src.domain.exceptions.base import VectorStoreException, WorkflowConflictError
from src.infrastructure.database.repositories import InMemoryAuditLogRepository
from src.infrastructure.embeddings.mock_embeddings import MockEmbeddingProvider
from src.infrastructure.llm.mock_provider import MockLLMProvider
from src.infrastructure.vector_store.memory_store import MemoryVectorStore

DISPATCH_QUERY = "Optimize battery storage and precool Lecture Hall 1 to 23.5 C to eliminate peak penalty."
SECRET = 'host "ep-secret-pooler.neon.tech" user=campusgrid_user'


# ---------------------------------------------------------------------------
# Intent routing
# ---------------------------------------------------------------------------

def test_mock_llm_router_abstains_so_off_topic_queries_stay_out_of_scope(test_container):
    assert LLMIntentRouter(MockLLMProvider()).route("Tell me a joke about cats") is None

    res = test_container.orchestrator.execute({"query": "Tell me a joke about cats", "user_id": "operator"})
    assert res.success, res.error
    assert res.data["status"] == "out_of_scope"
    assert res.data["requires_human_approval"] is False


@pytest.mark.parametrize("query,expected", [
    ("What are the peak rates?", ACTION_POLICY_LOOKUP),
    ("What are the tariffs?", ACTION_POLICY_LOOKUP),
    ("What is the peak rate?", ACTION_POLICY_LOOKUP),
    ("Show the load forecasts for tomorrow", ACTION_TELEMETRY_STATUS),
    ("How should the batteries run overnight?", ACTION_OPTIMIZE_DISPATCH),
])
def test_rule_intents_accept_plural_keywords(query, expected):
    action, confidence = NLPQueryParser().classify_intent(query.lower())
    assert action == expected
    assert confidence >= 0.6  # confident enough that the LLM router is not consulted


# ---------------------------------------------------------------------------
# Error text never reaches clients (it is logged server-side instead)
# ---------------------------------------------------------------------------

def test_unexpected_agent_errors_are_logged_not_returned(client, test_container, monkeypatch, caplog):
    class _BrokenMeterRepo:
        def get_historical_profile(self, date_str):
            raise RuntimeError(f"could not connect to server at {SECRET}")

    monkeypatch.setattr(test_container.agent1_telemetry, "meter_repo", _BrokenMeterRepo())
    with caplog.at_level(logging.ERROR, logger="campusgrid.agents"):
        resp = client.get("/api/telemetry/forecast")

    assert resp.status_code == 502
    assert SECRET not in resp.text
    assert "Agent 1" in resp.json()["message"] and "RuntimeError" in resp.json()["message"]
    assert SECRET in caplog.text


def test_provider_errors_are_logged_not_returned(client, test_container, monkeypatch, caplog):
    def _failing(*args, **kwargs):
        raise VectorStoreException(
            message=f"pgvector similarity search failed: {SECRET}",
            provider_name="pgvector",
            details={"original_error": SECRET},
        )

    monkeypatch.setattr(test_container.agent3_rag.retrieval_service, "search", _failing)
    monkeypatch.setattr(test_container.retrieval_service, "ingest_raw_document", _failing)
    with caplog.at_level(logging.WARNING):
        through_agent = client.post("/api/rag/search", json={"query": "peak tariff rate"})
        direct = client.post("/api/rag/ingest", json={"text": "### Clause 9.9: New rate\nPeak LKR 60.00 per kWh."})

    assert through_agent.status_code == 502 and SECRET not in through_agent.text
    assert direct.status_code == 502 and SECRET not in direct.text
    assert direct.json()["details"] == {"provider": "pgvector"}
    assert SECRET in caplog.text


# ---------------------------------------------------------------------------
# Human approval: one decision per plan, even under concurrency
# ---------------------------------------------------------------------------

def test_concurrent_decisions_on_one_plan_record_exactly_one():
    class _SlowDecisionLookupRepo(InMemoryAuditLogRepository):
        def get_decision_for(self, log_id):
            decision = super().get_decision_for(log_id)
            time.sleep(0.05)  # widen the check-then-append window
            return decision

    repo = _SlowDecisionLookupRepo()
    service = AuditService(audit_repo=repo)
    log_id = repo.log_transaction(AuditRecord(
        user_id="operator", query_text="plan", agent_sequence={}, final_decision={},
        record_type=RECORD_DISPATCH_RECOMMENDATION, approval_status=APPROVAL_PENDING,
    ))

    outcomes = []

    def decide(approved: bool):
        try:
            service.record_decision(log_id, approver_id="admin", approved=approved, notes="reviewed")
            outcomes.append("recorded")
        except WorkflowConflictError:
            outcomes.append("conflict")

    threads = [threading.Thread(target=decide, args=(flag,)) for flag in (True, False)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(outcomes) == ["conflict", "recorded"]
    decisions = [r for r in repo.list_all_ascending() if r.record_type == RECORD_APPROVAL_DECISION]
    assert len(decisions) == 1


# ---------------------------------------------------------------------------
# Comfort verdict fails closed
# ---------------------------------------------------------------------------

def test_missing_comfort_verdict_is_reported_as_unverified(test_container):
    class _NoVerdictTwin(BaseAgent):
        def __init__(self):
            super().__init__(name="Agent 2 stub", description="returns temperatures but no verdict")

        def _run(self, input_data):
            return {"simulated_indoor_temps_c": [24.0] * 48}

    orchestrator = CampusGridOrchestrator(
        agent1_telemetry=test_container.agent1_telemetry,
        agent2_twin=_NoVerdictTwin(),
        agent3_rag=test_container.agent3_rag,
        agent4_dispatch=test_container.agent4_dispatch,
        audit_repo=InMemoryAuditLogRepository(),
        nlp_parser=test_container.nlp_parser,
    )
    res = orchestrator.execute({"query": DISPATCH_QUERY, "user_id": "operator"})
    assert res.success, res.error
    rec = res.data["recommendation"]
    assert rec["thermal_feasibility"]["is_feasible"] is False
    assert any("unverified" in w for w in rec["warnings"])


# ---------------------------------------------------------------------------
# Knowledge base does not depend on the working directory
# ---------------------------------------------------------------------------

def test_corpus_is_found_from_any_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    service = RetrievalService(vector_store=MemoryVectorStore(), embedding_provider=MockEmbeddingProvider())
    stats = service.index_stats()
    assert stats["total_clauses"] > len(_FALLBACK_CLAUSES)
    assert {d["source_document"] for d in stats["documents"]} >= {"ASHRAE Standard 55-2023", "PUCSL Electricity Tariff Schedule GP-2"}


# ---------------------------------------------------------------------------
# Input sanitization covers every JSON media type
# ---------------------------------------------------------------------------

def test_plus_json_bodies_are_sanitized_before_reaching_agents(client):
    body = json.dumps({"query": "peak\u0000 tariff ​ rate", "top_k": 1}).encode()
    resp = client.post("/api/rag/search", content=body, headers={"Content-Type": "application/vnd.api+json"})
    assert resp.status_code == 200
    assert resp.json()["data"]["query"] == "peak tariff  rate"


def test_body_without_content_type_is_sanitized():
    """Older FastAPI releases parse a body with no Content-Type as JSON, so it must be sanitized too."""
    received = {}

    async def app(scope, receive, send):
        received["body"] = (await receive())["body"]

    raw = json.dumps({"query": "peak\u0000 rate​"}).encode()
    messages = [{"type": "http.request", "body": raw, "more_body": False}]

    async def receive():
        return messages.pop(0)

    async def send(message):
        pass

    scope = {"type": "http", "method": "POST", "path": "/api/rag/search", "query_string": b"", "headers": []}
    asyncio.run(InputSanitizationMiddleware(app)(scope, receive, send))
    assert json.loads(received["body"]) == {"query": "peak rate"}


# ===========================================================================
# Approved follow-up changes (B-numbers refer to the September 2026 review)
# ===========================================================================

from src.agents.dispatch_explanation.agent import DispatchExplanationAgent
from src.agents.dispatch_explanation.faithfulness import FaithfulnessVerifier
from src.agents.dispatch_explanation.milp_solver import CampusMicrogridOptimizer
from src.agents.dispatch_explanation.xai_explainer import XAIExplainer
from src.agents.digital_twin.agent import DigitalTwinAgent
from src.agents.digital_twin.thermal_model import BuildingThermalTwin
from src.agents.telemetry.forecaster import DemandForecaster
from src.agents.telemetry.summary import build_forecast_summary
from src.config.settings import Settings
from src.application.container import Container
from src.domain.entities.optimization import OptimizationInput
from src.domain.entities.telemetry import TelemetryInterval
from src.domain.interfaces.llm import LLMProvider
from src.infrastructure.cache.factory import CacheProviderFactory
from src.infrastructure.llm.factory import resolve_model
from src.infrastructure.reference_baselines import BaselineBuildingThermalTwin
from src.infrastructure.tools.weather_tool import WeatherTool
from src.infrastructure.vector_store.factory import VectorStoreFactory
from src.config.settings import CacheSettings, VectorStoreSettings
from src.shared.datetime_utils import build_tou_tariff_profile, get_standard_48_time_slots

SLOTS = get_standard_48_time_slots()
EVENING_PEAK_LOAD = [200.0 if i < 16 else (650.0 if 36 <= i < 45 else 420.0) for i in range(48)]
TARIFFS = build_tou_tariff_profile(SLOTS, 58.0, 30.0, 15.0)
TARIFF_SUMMARY = {
    "rates_lkr_kwh": {"peak": 61.5, "day": 30.0, "off_peak": 15.0},
    "windows": {"peak": "18:00 - 22:30", "day": "05:30 - 18:00", "off_peak": "22:30 - 05:30"},
    "max_demand_penalty_lkr_kva": 1100.0,
}


def _dispatch_input(**extra):
    return {"time_slots": SLOTS, "forecast_demand_kw": EVENING_PEAK_LOAD, "forecast_solar_kw": [0.0] * 48,
            "tariffs_lkr_kwh": TARIFFS, "citations": [], "user_query": "cut the peak", **extra}


class _DownLLM(LLMProvider):
    """A provider outage: every call fails."""
    def generate(self, messages, temperature=None, max_tokens=None, model_override=None):
        raise ConnectionError("provider unreachable")

    async def generate_async(self, messages, temperature=None, max_tokens=None, model_override=None):
        raise ConnectionError("provider unreachable")

    def get_model_info(self):
        return {"provider": "down"}


class _InventingExplainer:
    def generate_explanation(self, solver_output, citations, user_query, tariff_summary=None, comfort_feasible=None):
        return "The plan cuts the peak from 820.0 kW to 720.0 kW and saves LKR 43,500 (14.8%) at 19:15."


# --- B1: fact-checker fails closed and checks every number -------------------------------------

def test_fact_check_rejects_invented_numbers_even_when_the_model_says_faithful():
    agent = DispatchExplanationAgent(llm_provider=MockLLMProvider(), explainer=_InventingExplainer())
    audit = agent.execute(_dispatch_input()).data["faithfulness_audit"]
    assert audit["is_faithful"] is False
    assert set(audit["checks"]["numbers"]["unsupported"]) >= {"820.0", "720.0", "43,500", "14.8", "19:15"}


def test_fact_check_fails_closed_when_the_model_reply_is_unreadable():
    solver = CampusMicrogridOptimizer().solve(OptimizationInput(
        time_slots=SLOTS, base_load_kw=EVENING_PEAK_LOAD, solar_gen_kw=[0.0] * 48, grid_tariff_lkr_kwh=TARIFFS))
    grounded = f"Savings are LKR {solver.net_savings_lkr:,.2f} ({solver.savings_percentage:.1f}%)."
    unreadable = FaithfulnessVerifier(MockLLMProvider(default_response="Looks fine to me!")).verify(grounded, solver)
    assert unreadable["is_faithful"] is False and unreadable["checks"]["model"]["passed"] is None
    fenced = FaithfulnessVerifier(MockLLMProvider(
        default_response='```json\n{"is_faithful": true, "confidence": 0.9, "reasoning": "ok"}\n```')).verify(grounded, solver)
    assert fenced["is_faithful"] is True


# --- B4 / B11 / B5: solver economics -------------------------------------------------------------

def test_solver_keeps_end_of_day_charge_and_reports_the_full_saving():
    solver = CampusMicrogridOptimizer().solve(OptimizationInput(
        time_slots=SLOTS, base_load_kw=EVENING_PEAK_LOAD, solar_gen_kw=[0.0] * 48, grid_tariff_lkr_kwh=TARIFFS))
    assert solver.battery_soc_kwh[-1] >= 0.5 * 500.0 - 1e-6  # started at 50% of 500 kWh
    assert solver.demand_charge_savings_lkr > 0
    assert abs(solver.net_savings_lkr - (solver.energy_savings_lkr + solver.demand_charge_savings_lkr)) < 0.02
    assert abs(solver.net_savings_lkr - (solver.baseline_cost_lkr - solver.optimized_cost_lkr)) < 0.02


def test_agent4_uses_the_demand_charge_and_battery_limits_it_is_given():
    agent = DispatchExplanationAgent(llm_provider=MockLLMProvider())
    for charge in (100.0, 5000.0):
        solver = agent.execute(_dispatch_input(max_demand_penalty_lkr_kva=charge)).data["solver_output"]
        shaved = solver["peak_demand_baseline_kw"] - solver["peak_demand_optimized_kw"]
        assert shaved > 0
        assert abs(solver["demand_charge_savings_lkr"] - shaved * charge / 30.0) < 0.05  # the charge it was given

    limited = agent.execute(_dispatch_input(max_discharge_rate_kw=40.0)).data
    assert max(limited["solver_output"]["battery_discharge_kw"]) <= 40.0 + 1e-6
    assert limited["battery_parameters"]["max_discharge_rate_kw"] == 40.0


# --- B13 / B12: explanation degrades gracefully and is fed only verified inputs ------------------

def test_llm_outage_still_produces_a_plan_marked_unverified():
    data = DispatchExplanationAgent(llm_provider=_DownLLM()).execute(_dispatch_input())
    assert data.success, data.error
    assert data.data["explanation_source"] == "solver_template"
    assert data.data["faithfulness_audit"]["checks"]["numbers"]["passed"] is True
    assert data.data["faithfulness_audit"]["is_faithful"] is False  # the model audit could not run


def test_explanation_prompt_carries_retrieved_tariff_and_comfort_verdict():
    llm = MockLLMProvider()
    solver = CampusMicrogridOptimizer().solve(OptimizationInput(
        time_slots=SLOTS, base_load_kw=EVENING_PEAK_LOAD, solar_gen_kw=[0.0] * 48, grid_tariff_lkr_kwh=TARIFFS))
    text = XAIExplainer(llm).generate_explanation(solver, [], "cut the peak", TARIFF_SUMMARY, comfort_feasible=False)
    prompt = llm.call_history[-1][-1].content
    assert "LKR 61.50/kWh (18:00 - 22:30)" in prompt and "58.00" not in prompt
    assert "Comfort NOT confirmed" in prompt
    assert "did not confirm the comfort band" in text


def test_default_offline_plan_is_grounded_and_passes_the_fact_check(test_container):
    res = test_container.orchestrator.execute({"query": DISPATCH_QUERY, "user_id": "operator"})
    rec = res.data["recommendation"]
    assert rec["faithfulness_audit"]["is_faithful"] is True
    assert f"{rec['solver_summary']['net_savings_lkr']:,.2f}" in rec["explanation"]


# --- B17 / B18: configuration that cannot be honoured stops startup ------------------------------

def test_llm_provider_and_model_must_agree():
    assert resolve_model("gemini", "gemini/gemini-3.5-flash") == "gemini/gemini-3.5-flash"
    assert resolve_model("openai", "gpt-4o-mini") == "openai/gpt-4o-mini"
    assert resolve_model("litellm", "groq/llama3") == "groq/llama3"
    with pytest.raises(ValueError):
        resolve_model("openai", "gemini/gemini-3.5-flash")
    with pytest.raises(ValueError):
        resolve_model("gemnii", "gemini/gemini-3.5-flash")


def test_unsupported_storage_settings_are_rejected():
    with pytest.raises(ValueError):
        VectorStoreFactory.create(VectorStoreSettings(provider="qdrant"))
    with pytest.raises(ValueError):
        VectorStoreFactory.create(VectorStoreSettings(provider="pgvector"), engine=None)
    with pytest.raises(ValueError):
        CacheProviderFactory.create(CacheSettings(provider="redis"))
    with pytest.raises(ValueError):
        Container(Settings(app_env="test", vector_store_provider="pgvector", database_provider="in_memory"))


# --- B20 / B21: 2R2C physics and the thermostat -------------------------------------------------

def test_thermal_model_follows_the_srs_2r2c_equations():
    # Hand-computed from SRS 6.1 with c_in=50, r_vent=2.5, c_wall=200, r_in=2, r_out=6, dt=0.5 h.
    assert BuildingThermalTwin().simulate(24.0, [30.0, 30.0], [10, 10], [0.0, 0.0]) == [24.03, 24.06]
    heatwave = [34.0] * 24 + [24.0] * 12
    with_wall = BuildingThermalTwin().simulate(24.0, heatwave, [0] * 36, [0.0] * 36)
    wall_decoupled = BuildingThermalTwin(r_in=1e9).simulate(24.0, heatwave, [0] * 36, [0.0] * 36)
    assert max(with_wall) < max(wall_decoupled)  # the envelope's thermal mass buffers the room


def test_twin_holds_the_requested_setpoint_and_reads_comfort_limits_from_its_input():
    agent = DigitalTwinAgent()
    base = {"initial_temp_c": 23.5, "ambient_temperatures_c": [33.0] * 12, "occupancy_counts": [200] * 12,
            "target_setpoint_c": 23.5}
    held = agent.execute(base).data
    assert held["hvac_mode"] == "thermostat" and max(held["simulated_indoor_temps_c"]) <= 23.5
    assert held["is_thermal_feasible"] is True

    undersized = DigitalTwinAgent(hvac_max_cooling_kw=5.0).execute(base).data
    assert max(undersized["simulated_indoor_temps_c"]) > 23.5

    strict = agent.execute({**base, "comfort_max_c": 23.0}).data
    assert strict["comfort_violations_count"] > 0


# --- B22: MCP over HTTP with the container's own tools ------------------------------------------

def test_mcp_endpoint_serves_the_containers_tools(client, auditor_client, anon_client, test_container):
    assert isinstance(test_container.simulation_tool.thermal_twin, BaselineBuildingThermalTwin)  # baselines in tests
    listed = client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).json()
    names = {t["name"] for t in listed["result"]["tools"]}
    assert names == {"simulate_building_thermal_dynamics", "get_campus_weather_forecast"}

    spoofed = client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
        "name": "simulate_building_thermal_dynamics",
        "arguments": {"initial_temp_c": -15.0, "ambient_temps": [24.0], "occupant_counts": [1], "hvac_power_kw": [1.0]}}})
    assert spoofed.json()["result"]["isError"] is True
    injected = client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
        "name": "get_campus_weather_forecast", "arguments": {"date": "2026-01-01&latitude=0"}}})
    assert injected.json()["result"]["isError"] is True

    assert client.post("/api/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}).status_code == 202
    assert auditor_client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 4, "method": "tools/list"}).status_code == 403
    assert anon_client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 5, "method": "tools/list"}).status_code == 401


# --- B2 / B3 / B9 / B29: Agent 1 --------------------------------------------------------------

def test_weather_request_for_a_date_is_one_open_meteo_accepts(monkeypatch):
    seen = {}

    class _Reply:
        def __init__(self, temps):
            self.body = json.dumps({"hourly": {"temperature_2m": temps}}).encode()

        def read(self):
            return self.body

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        return _Reply([27.0] * 24 if "2026-10-01" in request.full_url else [None] * 24)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    tool = WeatherTool()
    assert tool.execute(date="2026-10-01").data["source"] == "open-meteo"
    assert "start_date=2026-10-01" in seen["url"] and "forecast_days" not in seen["url"]
    assert tool.execute(date="2026-07-20").data["source"] == "offline-fallback"  # nulls, not a crash


def test_forecaster_does_not_extrapolate_beyond_its_training_range():
    forecaster = DemandForecaster()
    interval = TelemetryInterval(time_slot="14:00", base_load_kw=500.0, solar_gen_kw=0.0, outdoor_temp_c=30.0,
                                 grid_tariff_lkr_kwh=30.0, zone_occupancy_count=0)
    top_of_range = forecaster._model_artifact["feature_ranges"]["occupancy_count"][1]
    at_limit = forecaster.predict([interval], [30.0], [top_of_range]).forecast_demand_kw[0]
    far_beyond = forecaster.predict([interval], [30.0], [1650]).forecast_demand_kw[0]
    assert far_beyond == at_limit


def test_agent1_uses_the_target_weekday_and_room_timetable(test_container):
    agent = test_container.agent1_telemetry
    monday = agent.execute({"date": "2026-09-28", "room": "LH-1"}).data
    saturday = agent.execute({"date": "2026-09-26", "room": "LH-1"}).data
    slot = monday["time_slots"].index("13:00")
    assert monday["day_of_week"] == 1 and monday["occupancy_counts"][slot] == 240
    assert saturday["day_of_week"] == 6 and max(saturday["occupancy_counts"]) == 0  # an empty room stays empty
    assert monday["campus_occupancy_counts"][slot] > 240  # the forecaster still sees campus load
    bad = agent.execute({"date": "2026-02-30", "room": "LH-1"})
    assert not bad.success and "VALIDATION_ERROR" in bad.error


def test_forecast_summary_survives_a_missing_temperature_series():
    summary = build_forecast_summary(MockLLMProvider(), ["12:00"], [500.0], [], [])
    assert summary is not None


def test_privacy_export_is_fixed_per_date(test_container):
    agent = test_container.agent1_telemetry
    first = agent.get_privacy_protected_export("2026-09-10")
    assert agent.get_privacy_protected_export("2026-09-10") == first
    raw = test_container.meter_repo.get_historical_profile("2026-09-10")
    assert first != raw


# --- B10: training pipeline --------------------------------------------------------------------

def test_trainer_never_writes_a_pickle_into_the_json_model(tmp_path):
    pytest.importorskip("joblib")
    from src.pipelines.periodic_retraining.train_forecaster import ModelTrainer
    target = tmp_path / "model_forecaster.json"
    ModelTrainer._save_artifact({"not": "a linear model"}, "lightgbm", {"feature_ranges": {}}, str(target))
    assert not target.exists()
    assert (tmp_path / "model_forecaster.lightgbm.joblib").exists()


def test_trainer_baseline_is_the_reference_persistence_forecast():
    from src.pipelines.periodic_retraining.train_forecaster import ModelTrainer
    row = lambda d, load: {"reading_date": d, "time_slot": "10:00", "base_load_kw": load,
                           "outdoor_temp_c": 30.0, "zone_occupancy_count": 100}
    rows = [row("2026-06-01", 400.0), row("2026-06-02", 999.0)]
    # previous day's reading + 15 kW/°C above 28 °C + 0.05 kW per occupant
    assert ModelTrainer._baseline_predictions(rows, [rows[1]]) == [400.0 + 30.0 + 5.0]


# --- B23 / B30 / B31 / B32 / B35 / B36 / B19 ----------------------------------------------------

def test_parser_seed_rooms_carry_capacities():
    assert NLPQueryParser().rooms["LH-1"]["max_capacity"] == 250


def test_role_list_needs_a_token(anon_client, auditor_client):
    assert anon_client.get("/api/auth/roles").status_code == 401
    assert auditor_client.get("/api/auth/roles").status_code == 200


def test_impossible_dates_are_rejected(client):
    assert client.get("/api/telemetry/historical", params={"date": "2026-13-45"}).status_code == 422
    assert client.get("/api/telemetry/forecast", params={"date": "2026-02-30"}).status_code == 422
    assert client.post("/api/simulation/what-if", json={"date": "2026-02-30"}).status_code == 422
    assert client.get("/api/telemetry/historical").status_code == 200


def test_plan_record_can_be_fetched_without_agent_outputs(client):
    log_id = client.post("/api/orchestrator/query", json={"query": DISPATCH_QUERY}).json()["data"]["audit_log_id"]
    slim = client.get(f"/api/audit/logs/{log_id}", params={"include_details": "false"}).json()["data"]
    full = client.get(f"/api/audit/logs/{log_id}").json()["data"]
    assert "agent_sequence" not in slim and "agent_sequence" in full
    assert slim["final_decision"] == full["final_decision"]


def test_slow_agent3_times_out_instead_of_hanging(test_container):
    release, finished = threading.Event(), threading.Event()

    class _SlowRag(BaseAgent):
        def __init__(self):
            super().__init__(name="Agent 3 stub", description="never answers in time")

        def _run(self, input_data):
            release.wait(5.0)
            return {}

        def cleanup(self):
            finished.set()

    orchestrator = CampusGridOrchestrator(
        agent1_telemetry=test_container.agent1_telemetry, agent2_twin=test_container.agent2_twin,
        agent3_rag=_SlowRag(), agent4_dispatch=test_container.agent4_dispatch,
        audit_repo=InMemoryAuditLogRepository(), nlp_parser=test_container.nlp_parser, agent3_timeout_seconds=0.2,
    )
    res = orchestrator.execute({"query": DISPATCH_QUERY, "user_id": "operator"})
    release.set()
    finished.wait(5.0)  # let the abandoned worker finish before the test's log capture closes
    assert not res.success and "no answer within" in res.error


def test_policy_agent_output_has_no_always_empty_fields(test_container):
    assert "matched_passages" not in test_container.agent3_rag.execute({"query": "peak tariff"}).data


def test_env_example_runs_every_member_slice():
    settings = Settings(_env_file=".env.example", app_env="test")
    assert settings.baseline_agents == set()
