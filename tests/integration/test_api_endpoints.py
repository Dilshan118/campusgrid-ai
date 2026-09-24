"""
Integration tests for FastAPI REST endpoints using TestClient.
"""

def test_api_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "active_providers" in data

def test_api_telemetry_forecast(client):
    response = client.get("/api/telemetry/forecast?date=2026-09-06&room=LH-1")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "forecast_demand_kw" in data["data"]
    assert len(data["data"]["forecast_demand_kw"]) == 48

def test_api_simulation_what_if(client):
    payload = {
        "initial_temp_c": 24.0,
        "ambient_temp_delta_c": 2.0,
        "occupancy_multiplier": 1.2
    }
    response = client.post("/api/simulation/what-if", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "simulated_indoor_temps_c" in data["data"]

def test_api_optimizer_dispatch(client):
    payload = {
        "battery_capacity_kwh": 500.0,
        "max_charge_rate_kw": 100.0,
        "max_discharge_rate_kw": 100.0,
        "initial_soc_ratio": 0.50
    }
    response = client.post("/api/optimizer/dispatch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["net_savings_lkr"] >= 0.0

def test_api_rag_search(client):
    payload = {"query": "PUCSL peak tariff hours", "top_k": 2}
    response = client.post("/api/rag/search", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]["citations"]) >= 1

def test_api_orchestrator_query(client):
    payload = {
        "query": "Schedule battery discharge to shave evening peak demand",
        "user_id": "test_operator"
    }
    response = client.post("/api/orchestrator/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "recommendation" in data["data"]
    assert "explanation" in data["data"]

def test_api_audit_logs(client):
    response = client.get("/api/audit/logs?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)

def test_api_rag_ingest(client):
    payload = {
        "text": "### Clause 9.9: Emergency Generator Operations\nEmergency diesel generators shall only be dispatched if the microgrid battery SOC drops below 15%.",
        "source_document": "Campus Energy Contingency Plan 2026",
        "effective_date": "2026-01-01"
    }
    response = client.post("/api/rag/ingest", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["clauses_added"] >= 1

def test_api_auth_login_and_me(client):
    # Test valid login
    login_resp = client.post("/api/auth/login", json={"username": "admin", "password": "campusgrid2026"})
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert data["success"] is True
    token = data["data"]["access_token"]
    assert token is not None
    assert data["data"]["role"] == "FACILITY_MANAGER"

    # Test /me with Bearer token
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["success"] is True
    assert me_data["data"]["user_id"] == "admin"
    assert me_data["data"]["role"] == "FACILITY_MANAGER"

def test_api_auth_invalid_credentials(client):
    login_resp = client.post("/api/auth/login", json={"username": "admin", "password": "wrong_password"})
    assert login_resp.status_code == 401 or login_resp.status_code == 400


