"""
CampusGrid AI: Pytest Fixtures & Test Setup
Hermetic test configuration using mock providers and in-memory stores.
"""

import pytest
import os
import sys
from fastapi.testclient import TestClient

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config.settings import Settings
from src.application.container import Container, get_container
from src.api.main import app
from src.api.middleware.auth import (
    create_access_token,
    ROLE_FACILITY_MANAGER,
    ROLE_OPERATOR,
    ROLE_AUDITOR,
)

@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return Settings(
        app_env="test",
        llm_provider="mock",
        embedding_provider="mock",
        vector_store_provider="memory",
        database_provider="in_memory",
        cache_provider="memory",
        reranker_strategy="rrf",
        use_reference_baselines=True
    )

@pytest.fixture(scope="session")
def test_container(test_settings: Settings) -> Container:
    return get_container(test_settings)

def _client_as(user_id: str, role: str) -> TestClient:
    token = create_access_token(user_id=user_id, role=role)
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


@pytest.fixture(scope="session")
def client(test_container: Container) -> TestClient:
    """Authenticated as a facility manager (every endpoint is permitted)."""
    return _client_as("admin", ROLE_FACILITY_MANAGER)


@pytest.fixture(scope="session")
def operator_client(test_container: Container) -> TestClient:
    return _client_as("operator", ROLE_OPERATOR)


@pytest.fixture(scope="session")
def auditor_client(test_container: Container) -> TestClient:
    return _client_as("auditor", ROLE_AUDITOR)


@pytest.fixture(scope="session")
def anon_client(test_container: Container) -> TestClient:
    """No bearer token at all."""
    return TestClient(app)
