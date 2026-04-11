"""Integration tests for the API with real MongoDB.

Run with: pytest tests/integration/test_api_integration.py -v
Requires: docker compose up -d
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from terrain.api.routes import candidates, interesting_companies, opportunities, pipeline
from terrain.providers.db.mongo import MongoDatabaseClient

TEST_DB_URI = "mongodb://localhost:27017/terrain_test_api"


def _create_test_app() -> FastAPI:
    """Create a test app that initializes DB in its own lifespan (same event loop)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        db = MongoDatabaseClient(TEST_DB_URI)
        await db.initialize()
        app.state.db = db
        app.state.anthropic = None
        app.state.ollama = MagicMock()
        app.state.ollama.check_health = AsyncMock(return_value=False)
        app.state.scheduler = MagicMock()
        app.state.scheduler.is_running = False
        app.state.scheduler.get_jobs = MagicMock(return_value=[])
        app.state.stages = {}
        yield
        await db._db.drop_collection("opportunities")
        await db._db.drop_collection("candidates")
        await db._db.drop_collection("pipeline_runs")
        await db._db.drop_collection("api_usage")
        await db._db.drop_collection("interesting_companies")
        db.close()

    test_app = FastAPI(lifespan=lifespan)
    test_app.include_router(opportunities.router)
    test_app.include_router(pipeline.router)
    test_app.include_router(candidates.router)
    test_app.include_router(interesting_companies.router)

    from terrain.api.main import HealthResponse, health

    @test_app.get("/api/health")
    async def test_health() -> dict:
        try:
            await test_app.state.db._db.command("ping")
            db_status = "connected"
        except Exception:
            db_status = "error"
        return {"status": "healthy" if db_status == "connected" else "degraded",
                "environment": "development", "database": db_status,
                "ollama": "not_connected", "scheduler": "stopped", "uptime_seconds": 0.0}

    return test_app


@pytest.fixture
def client() -> TestClient:
    test_app = _create_test_app()
    with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
        with TestClient(test_app) as c:
            yield c


@pytest.mark.integration
class TestOpportunityAPIIntegration:
    def test_create_and_list(self, client: TestClient) -> None:
        resp = client.post(
            "/api/opportunities",
            json={
                "company": "Acme Corp",
                "title": "Senior Data Engineer",
                "description_text": "Build the data org.",
            },
        )
        assert resp.status_code == 201
        opp_id = resp.json()["id"]

        resp = client.get("/api/opportunities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["company"] == "Acme Corp"

        resp = client.get(f"/api/opportunities/{opp_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Senior Data Engineer"

    def test_update_notes(self, client: TestClient) -> None:
        resp = client.post(
            "/api/opportunities",
            json={"company": "Test", "title": "Test", "description_text": "Test"},
        )
        opp_id = resp.json()["id"]

        resp = client.patch(
            f"/api/opportunities/{opp_id}/notes",
            json={"notes": "Called recruiter today."},
        )
        assert resp.status_code == 200

        resp = client.get(f"/api/opportunities/{opp_id}")
        assert resp.json()["notes"] == "Called recruiter today."

    def test_filter_by_company(self, client: TestClient) -> None:
        client.post("/api/opportunities", json={"company": "Acme", "title": "A", "description_text": "X"})
        client.post("/api/opportunities", json={"company": "Beta", "title": "B", "description_text": "Y"})

        resp = client.get("/api/opportunities?company=Acme")
        assert resp.json()["count"] == 1

    def test_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/opportunities/507f1f77bcf86cd799439011")
        assert resp.status_code == 404


@pytest.mark.integration
class TestInterestingCompaniesAPIIntegration:
    def test_crud_cycle(self, client: TestClient) -> None:
        resp = client.post(
            "/api/interesting-companies",
            json={
                "company_name": "Acme Corp",
                "interest_drivers": ["great data team"],
                "notes": "Recruiter reached out",
            },
        )
        assert resp.status_code == 201
        company_id = resp.json()["id"]

        resp = client.get("/api/interesting-companies")
        assert resp.json()["count"] == 1

        resp = client.patch(
            f"/api/interesting-companies/{company_id}",
            json={"notes": "Updated notes"},
        )
        assert resp.status_code == 200

        resp = client.delete(f"/api/interesting-companies/{company_id}")
        assert resp.status_code == 204

        resp = client.get("/api/interesting-companies")
        assert resp.json()["count"] == 0


@pytest.mark.integration
class TestHealthIntegration:
    def test_health_with_real_db(self, client: TestClient) -> None:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["database"] == "connected"
