"""
System-level robustness: slices developed in parallel by different members, concurrent requests
sharing one container, and the caches that sit between them.
"""

import inspect
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.api.main import app
from src.application.container import Container
from src.config.settings import Settings

PLAN_QUERY = "Precool Lecture Hall 1 to 23.5 C tomorrow and cut the peak demand charge"


def _container(**overrides) -> Container:
    return Container(Settings(app_env="test", **overrides))


def test_unfinished_member_slice_falls_back_automatically(monkeypatch):
    """A default install (no .env, no baseline switches) must still produce plans with all completed slices."""
    container = _container()
    status = container.slice_status()
    assert status["agent1_telemetry"] == "member_implementation"
    assert status["agent2_digital_twin"] == "member_implementation"
    assert status["agent4_dispatch"] == "member_implementation"
    res = container.orchestrator.execute({"query": PLAN_QUERY, "user_id": "admin"})
    assert res.success, res.error

    # Verify that if any member slice is unfinished (NotImplementedError), it falls back automatically
    monkeypatch.setattr("src.application.container._probe_thermal", lambda target: (_ for _ in ()).throw(NotImplementedError("Simulated unfinished physics")))
    fallback_container = _container()
    fallback_status = fallback_container.slice_status()
    assert fallback_status["agent2_digital_twin"] == "reference_baseline_auto"
    fallback_res = fallback_container.orchestrator.execute({"query": PLAN_QUERY, "user_id": "admin"})
    assert fallback_res.success, fallback_res.error


def test_fallback_can_be_switched_off_for_members_testing_their_own_code(monkeypatch):
    monkeypatch.setattr("src.agents.digital_twin.thermal_model.BuildingThermalTwin.simulate", lambda *args, **kwargs: (_ for _ in ()).throw(NotImplementedError("Member 3 physics under test")))
    container = _container(auto_baseline_fallback=False)
    assert container.slice_status()["agent2_digital_twin"] == "member_implementation"
    res = container.orchestrator.execute({"query": PLAN_QUERY, "user_id": "admin"})
    assert not res.success and "Agent 2" in res.error


def test_member_slices_receive_physics_settings():
    container = _container(battery_capacity_kwh=800.0, battery_max_power_kw=150.0)
    assert container.agent4_dispatch.optimizer.battery_cap_kwh == 800.0
    assert container.agent4_dispatch.optimizer.max_kw == 150.0
    assert container.agent2_twin.battery_dynamics.capacity_kwh == 800.0


def test_parallel_and_sequential_pipelines_give_identical_plans():
    container = _container(use_reference_baselines=True)
    results = []
    for parallel in (False, True):
        container.orchestrator.parallel_agents = parallel
        res = container.orchestrator.execute({"query": PLAN_QUERY, "user_id": "admin"})
        assert res.success, res.error
        rec = res.data["recommendation"]
        results.append((rec["net_savings_lkr"], rec["tariff_inputs"]["rates_lkr_kwh"], [c["section_clause"] for c in res.data["citations"]]))
    assert results[0] == results[1]


def test_concurrent_plans_searches_and_uploads_share_one_container_safely():
    container = _container(use_reference_baselines=True)
    service = container.retrieval_service
    before = service.index_stats()["total_clauses"]

    def plan(i):
        return container.orchestrator.execute({"query": f"{PLAN_QUERY} (run {i})", "user_id": "operator"}).success

    def search(i):
        return bool(service.search(f"peak tariff rate {i}", top_k=2)["citations"])

    def upload(i):
        return service.ingest_raw_document(
            f"### Clause 50.{i}: Contingency {i}\nGenerators may run when battery charge is below {10 + i} percent.",
            source_document=f"Contingency Plan {i}",
        )["clauses_added"]

    with ThreadPoolExecutor(max_workers=12) as pool:
        plans = list(pool.map(plan, range(8)))
        searches = list(pool.map(search, range(20)))
        uploads = list(pool.map(upload, range(6)))

    assert all(plans) and all(searches)
    assert uploads == [1] * 6
    assert service.index_stats()["total_clauses"] == before + 6
    assert container.vector_store.count() == before + 6
    assert container.audit_service.verify_chain()["valid"] is True
    assert len(container.audit_repo.list_recent(limit=100)) == 8


def test_search_cache_is_invalidated_by_an_upload():
    service = _container(use_reference_baselines=True).retrieval_service
    query = "diesel generator dispatch contingency"
    first = service.search(query, top_k=3)
    assert not any("Clause 77.1" in c["section_clause"] for c in first["citations"])

    service.ingest_raw_document(
        "### Clause 77.1: Diesel Generator Dispatch\nDiesel generator dispatch is a contingency measure only.",
        source_document="Contingency Plan",
    )
    second = service.search(query, top_k=3)
    assert any("Clause 77.1" in c["section_clause"] for c in second["citations"])


def test_cached_search_results_cannot_be_mutated_by_callers():
    service = _container(use_reference_baselines=True).retrieval_service
    result = service.search("peak tariff", top_k=1)
    result["citations"][0]["content"] = "tampered"
    assert service.search("peak tariff", top_k=1)["citations"][0]["content"] != "tampered"


def test_audit_list_uses_batched_decision_lookup():
    container = _container(use_reference_baselines=True)
    ids = [container.orchestrator.execute({"query": PLAN_QUERY, "user_id": "operator"}).data["audit_log_id"] for _ in range(3)]
    container.audit_service.record_decision(ids[0], "admin", approved=True, acknowledge_warnings=True)
    container.audit_service.record_decision(ids[1], "admin", approved=False, notes="Exam day")

    calls = {"single": 0}
    original = container.audit_repo.get_decision_for
    def counting(log_id):
        calls["single"] += 1
        return original(log_id)
    container.audit_repo.get_decision_for = counting

    views = {v["log_id"]: v for v in container.audit_service.list_views(limit=10, record_type="dispatch_recommendation")}
    assert calls["single"] == 0
    assert views[ids[0]]["effective_status"] == "approved"
    assert views[ids[1]]["effective_status"] == "rejected"
    assert views[ids[2]]["effective_status"] == "pending"


def _api_routes(routes):
    """Flattens routers, including FastAPI versions that wrap included routers instead of copying routes."""
    for route in routes:
        inner = getattr(route, "original_router", None)
        if inner is not None:
            yield from _api_routes(inner.routes)
        elif getattr(route, "path", "").startswith("/api/") and hasattr(route, "endpoint"):
            yield route


API_ROUTES = list(_api_routes(app.routes))


def test_every_router_is_discovered():
    assert len(API_ROUTES) >= 25


@pytest.mark.parametrize("route", API_ROUTES, ids=lambda r: f"{sorted(r.methods)[0]} {r.path}")
def test_route_handlers_do_not_block_the_event_loop(route):
    """Handlers call blocking code, so they must be plain `def` (run in FastAPI's thread pool)."""
    assert not inspect.iscoroutinefunction(route.endpoint), f"{route.path} is async def but calls blocking code"


def test_campus_headcounts_are_capped_to_the_room_before_the_comfort_check():
    """Agent 1's counts can be campus-wide; Agent 2 simulates one room. The hand-off caps them."""
    container = _container(use_reference_baselines=True)
    res = container.orchestrator.execute({"query": PLAN_QUERY, "user_id": "admin"})
    assert res.success, res.error
    capacity = container.room_repo.get_by_id("LH-1")["max_capacity"]
    assert max(res.data["digital_twin_feasibility"]["occupancy_counts"]) <= capacity
    assert any("capped" in note for note in res.data["assumptions"])
    assert res.data["recommendation"]["thermal_feasibility"]["is_feasible"] is True


def test_what_if_route_caps_occupancy_to_the_chosen_room(client):
    resp = client.post("/api/simulation/what-if", json={"room": "LAB-3", "occupancy_multiplier": 1.0})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["room"] == "LAB-3" and data["room_capacity"] == 80
    assert max(data["occupancy_counts"]) <= 80
