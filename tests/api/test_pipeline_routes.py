"""Tests for pipeline API routes — mocked stages and DB."""

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from terrain.api.main import app
from terrain.models.pipeline import PipelineStageEnum, StageResult


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
def mock_stage() -> AsyncMock:
    stage = AsyncMock()
    stage.run.return_value = StageResult(
        stage=PipelineStageEnum.SCORING,
        items_processed=5,
        items_new=3,
    )
    stage.run_one.return_value = StageResult(
        stage=PipelineStageEnum.SCORING,
        items_processed=1,
        items_new=1,
    )
    return stage


@pytest.fixture
def client(mock_db: MagicMock, mock_stage: AsyncMock) -> TestClient:
    app.state.db = mock_db
    app.state.anthropic = None
    app.state.ollama = MagicMock()
    app.state.ollama.check_health = AsyncMock(return_value=False)
    mock_scheduler = MagicMock()
    mock_scheduler.is_running = True
    mock_scheduler.enabled = True
    mock_scheduler.get_jobs.return_value = [{"id": "test_job", "next_run": "2026-04-10"}]
    mock_scheduler.get_active_runs.return_value = []
    mock_scheduler.trigger_manual = AsyncMock(return_value="run_123")
    app.state.scheduler = mock_scheduler
    app.state.stages = {"scoring": mock_stage}
    with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
        return TestClient(app, raise_server_exceptions=False)


class TestRunStage:
    def test_runs_stage_returns_immediately(self, client: TestClient) -> None:
        resp = client.post("/api/pipeline/scoring/run", json={"candidate_id": "candidate_1"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == "run_123"
        assert data["stage"] == "scoring"
        assert data["status"] == "running"

    def test_unknown_stage(self, client: TestClient) -> None:
        resp = client.post("/api/pipeline/unknown/run", json={"candidate_id": "candidate_1"})
        assert resp.status_code == 404


class TestRunStageOne:
    def test_runs_one(self, client: TestClient, mock_stage: AsyncMock) -> None:
        resp = client.post(
            "/api/pipeline/scoring/run-one",
            json={"candidate_id": "candidate_1", "opportunity_id": "opp1"},
        )
        assert resp.status_code == 200
        assert resp.json()["items_new"] == 1


class TestListRuns:
    def test_returns_runs(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.pipeline_runs.find_by_candidate.return_value = []
        resp = client.get("/api/pipeline/runs")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0


class TestSchedulerStatus:
    def test_returns_status(self, client: TestClient) -> None:
        resp = client.get("/api/pipeline/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["running"] is True
        assert data["enabled"] is True
        assert len(data["jobs"]) == 1
        assert data["active_runs"] == []


class TestCostSummary:
    def test_returns_costs(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.api_usage.get_cost_summary.return_value = {"scoring": 0.05, "cover_letter": 0.12}
        resp = client.get("/api/pipeline/costs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["costs_by_task"]["scoring"] == 0.05
