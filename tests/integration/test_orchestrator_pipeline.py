"""
Integration test for the full 4-Agent Sequential Coordination Pipeline.
"""

def test_central_orchestrator_pipeline(test_container):
    orchestrator = test_container.orchestrator

    query = "Optimize battery storage and precool Lecture Hall 1 to 23.5 C to eliminate peak penalty."
    res = orchestrator.execute({
        "query": query,
        "user_id": "test_facility_director"
    })

    assert res.success is True
    data = res.data

    assert data["status"] == "ready_for_operator_approval"
    assert data["requires_human_approval"] is True
    assert data["audit_log_id"] is not None
    assert "recommendation" in data
    assert "explanation" in data
    assert len(data["citations"]) >= 1

    # Verify audit trail recorded transaction
    audit_trail = test_container.audit_service.get_audit_trail(limit=5)
    assert len(audit_trail) >= 1
    assert audit_trail[0].user_id == "test_facility_director"

def test_orchestrator_policy_intent_branch(test_container):
    orchestrator = test_container.orchestrator
    query = "What are the PUCSL GP-2 peak tariff rates and demand penalty rules?"
    res = orchestrator.execute({
        "query": query,
        "user_id": "auditor_user"
    })
    assert res.success is True
    data = res.data
    assert data["status"] == "policy_info_retrieved"
    assert len(data["citations"]) >= 1
    assert data["requires_human_approval"] is False

def test_orchestrator_what_if_intent_branch(test_container):
    orchestrator = test_container.orchestrator
    query = "Simulate a +3C heatwave in Lecture Hall 1 with double occupancy."
    res = orchestrator.execute({
        "query": query,
        "user_id": "operator_user"
    })
    assert res.success is True
    data = res.data
    assert data["status"] == "simulation_completed"
    assert "digital_twin_feasibility" in data
    assert data["requires_human_approval"] is False

