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

@pytest.fixture(scope="session")
def client(test_container: Container) -> TestClient:
    return TestClient(app)
