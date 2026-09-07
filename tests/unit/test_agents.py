"""
Unit tests for the 4 Specialized Agents running in isolation.
Validates execution, output contract compliance, or graceful scaffold reporting.
"""

import pytest

def test_agent1_telemetry_forecasting(test_container):
    agent = test_container.agent1_telemetry
    res = agent.execute({"date": "2026-09-06", "room": "LH-1"})

    if not res.success and "NotImplementedError" in str(res.error):
        pytest.skip("Member 2 has not implemented Agent 1 forecaster yet.")

    assert res.success is True
    assert "forecast_demand_kw" in res.data
    assert len(res.data["forecast_demand_kw"]) == 48
    assert len(res.data["forecast_solar_kw"]) == 48

def test_agent2_digital_twin_simulation(test_container):
    agent = test_container.agent2_twin
    res = agent.execute({
        "initial_temp_c": 24.0,
        "ambient_temperatures_c": [28.0] * 48,
        "occupancy_counts": [50] * 48
    })

    if not res.success and "NotImplementedError" in str(res.error):
        pytest.skip("Member 3 has not implemented Agent 2 thermal model yet.")

    assert res.success is True
    assert "simulated_indoor_temps_c" in res.data
    assert len(res.data["simulated_indoor_temps_c"]) == 48

def test_agent3_policy_rag(test_container):
    """Member 1 (Team Lead) Hybrid RAG Agent - fully implemented."""
    agent = test_container.agent3_rag
    res = agent.execute({"query": "What is the PUCSL peak tariff rate?", "top_k": 2})

    assert res.success is True
    assert len(res.data["citations"]) >= 1
    assert res.data["peak_tariff_lkr"] == 58.00

def test_agent4_dispatch_explanation(test_container):
    agent = test_container.agent4_dispatch
    res = agent.execute({
        "time_slots": [f"{h:02d}:00" for h in range(24)],
        "forecast_demand_kw": [400.0] * 24,
        "forecast_solar_kw": [100.0] * 24,
        "tariffs_lkr_kwh": [30.0] * 24,
        "citations": [{"document_title": "PUCSL", "section_clause": "4.1", "content": "Tariff rule"}]
    })

    if not res.success and "NotImplementedError" in str(res.error):
        pytest.skip("Member 4 has not implemented Agent 4 MILP solver yet.")

    assert res.success is True
    assert "solver_output" in res.data
    assert "explanation" in res.data
    assert res.data["net_savings_lkr"] >= 0.0
