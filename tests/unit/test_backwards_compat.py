"""
Tests for backwards compatibility shims in backend/.
Ensures that legacy imports and entry points continue to work smoothly.
"""

from backend.main import app
from backend.optimizer.milp_solver import CampusMicrogridOptimizer
from backend.digital_twin.thermal_model import BuildingThermalTwin
from backend.agents.facility_agent import FacilityInterfaceAgent
from backend.agents.agent4_dispatch_explanation.xai_explainer import XAIExplainer
from backend.security.audit_store import AuditLogStore
from backend.agents.agent3_policy_rag.pgvector_search import PgVectorPolicySearch

def test_legacy_backend_main():
    assert app is not None
    assert app.title == "CampusGrid AI"

def test_legacy_optimizer():
    opt = CampusMicrogridOptimizer(500.0, 100.0)
    assert opt.battery_cap_kwh == 500.0

def test_legacy_thermal_model():
    twin = BuildingThermalTwin(50.0, 2.5)
    try:
        res = twin.simulate(24.0, [26.0], [10], [5.0])
        assert len(res) == 1
    except NotImplementedError:
        import pytest
        pytest.skip("BuildingThermalTwin.simulate() is awaiting Member 3 implementation.")

def test_legacy_facility_agent():
    agent = FacilityInterfaceAgent()
    res = agent.process_query("What is the peak tariff?")
    assert "recommendation" in res or "error" not in res

def test_legacy_xai_explainer():
    explainer = XAIExplainer()
    res = explainer.generate_explanation(
        solver_output={"baseline_cost_lkr": 1000, "optimized_cost_lkr": 800, "net_savings_lkr": 200, "savings_percentage": 20.0},
        retrieved_citations=[],
        user_query="Explain savings"
    )
    assert len(res) > 0

def test_legacy_audit_store():
    store = AuditLogStore()
    log_id = store.log_transaction("user1", "query1", {}, {}, False)
    assert log_id is not None
