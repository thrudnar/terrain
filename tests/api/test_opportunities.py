"""Tests for opportunity API routes — mocked DB."""

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from terrain.api.main import app
from terrain.models.opportunity import Opportunity, PipelineState, Source


def _make_opp(opp_id: str = "507f1f77bcf86cd799439011") -> Opportunity:
    return Opportunity(
        _id=opp_id,
        candidate_id="candidate_1",
        source=Source(
            board="linkedin",
            board_job_id="123",
            collection="top-applicant",
            url="https://linkedin.com/jobs/view/123",
            first_seen=datetime(2026, 4, 1, tzinfo=timezone.utc),
            last_seen=datetime(2026, 4, 1, tzinfo=timezone.utc),
        ),
        company="Acme Corp",
        title="Senior Data Engineer",
        description_text="Build data org.",
        pipeline_state=PipelineState.HARVESTED,
    )


@pytest.fixture
def mock_db() -> MagicMock:
    db = MagicMock()
    db.opportunities = AsyncMock()
    db.candidates = AsyncMock()
    db.pipeline_runs = AsyncMock()
    db.api_usage = AsyncMock()
    db.interesting_companies = AsyncMock()
    db._db = AsyncMock()
    return db


@pytest.fixture
def client(mock_db: MagicMock) -> TestClient:
    app.state.db = mock_db
    app.state.anthropic = None
    app.state.ollama = MagicMock()
    app.state.ollama.check_health = AsyncMock(return_value=False)
    app.state.scheduler = MagicMock()
    app.state.scheduler.is_running = False
    app.state.scheduler.get_jobs.return_value = []
    app.state.stages = {}
    with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
        return TestClient(app, raise_server_exceptions=False)


class TestListOpportunities:
    def test_returns_list(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.opportunities.find_for_ui.return_value = [_make_opp()]
        resp = client.get("/api/opportunities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["company"] == "Acme Corp"

    def test_empty_list(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.opportunities.find_for_ui.return_value = []
        resp = client.get("/api/opportunities")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_passes_filters(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.opportunities.find_for_ui.return_value = []
        client.get("/api/opportunities?pipeline_state=scored&company=Acme")
        call_args = mock_db.opportunities.find_for_ui.call_args[0]
        filters = call_args[1]
        assert filters.pipeline_state == PipelineState.SCORED
        assert filters.company == "Acme"


class TestGetOpportunity:
    def test_found(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.opportunities.get.return_value = _make_opp()
        resp = client.get("/api/opportunities/507f1f77bcf86cd799439011")
        assert resp.status_code == 200
        assert resp.json()["company"] == "Acme Corp"

    def test_not_found(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.opportunities.get.return_value = None
        resp = client.get("/api/opportunities/nonexistent")
        assert resp.status_code == 404


class TestUpdateNotes:
    def test_updates(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.opportunities.get.return_value = _make_opp()
        resp = client.patch(
            "/api/opportunities/507f1f77bcf86cd799439011/notes",
            json={"notes": "Called recruiter."},
        )
        assert resp.status_code == 200
        mock_db.opportunities.update_notes.assert_called_once()


class TestCreateOpportunity:
    def test_creates(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.opportunities.create.return_value = "new_id"
        resp = client.post(
            "/api/opportunities",
            json={
                "company": "NewCo",
                "title": "Director Data",
                "description_text": "A great role.",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["id"] == "new_id"
