"""Tests for the health endpoint."""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from terrain.api.main import app


@pytest.fixture
def client() -> TestClient:
    with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
        return TestClient(app)


class TestHealth:
    def test_returns_200(self, client: TestClient) -> None:
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_response_shape(self, client: TestClient) -> None:
        data = client.get("/api/health").json()
        assert "status" in data
        assert "environment" in data
        assert "database" in data
        assert "ollama" in data
        assert "scheduler" in data
        assert "uptime_seconds" in data
        assert data["status"] in ("healthy", "degraded")

    def test_uptime_is_positive(self, client: TestClient) -> None:
        data = client.get("/api/health").json()
        assert data["uptime_seconds"] >= 0
