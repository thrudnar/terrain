"""Tests for the pipeline scheduler."""

from unittest.mock import AsyncMock, patch

import pytest

from terrain.models.candidate import Candidate, ScheduleConfig
from terrain.models.pipeline import PipelineStageEnum, RunStatus, StageResult, TriggerType
from terrain.pipeline.scheduler import PipelineScheduler


def _make_candidate_with_schedules() -> Candidate:
    return Candidate(
        candidate_id="candidate_1",
        name="Test Candidate",
        schedules=ScheduleConfig(
            harvest_linkedin="0 8,20 * * *",
            score_batch="0 10,22 * * *",
        ),
    )


@pytest.fixture
def cand_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def run_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.create.return_value = "run_1"
    return repo


@pytest.fixture
def mock_stage() -> AsyncMock:
    stage = AsyncMock()
    stage.run.return_value = StageResult(
        stage=PipelineStageEnum.HARVEST,
        items_processed=10,
        items_new=5,
    )
    return stage


class TestSchedulerLoadSchedules:
    async def test_loads_schedules_from_candidate(
        self, cand_repo: AsyncMock, run_repo: AsyncMock
    ) -> None:
        cand_repo.get.return_value = _make_candidate_with_schedules()
        stages = {"harvest": AsyncMock(), "scoring": AsyncMock()}

        scheduler = PipelineScheduler(cand_repo, run_repo, stages)
        jobs_added = await scheduler.load_schedules("candidate_1")

        assert jobs_added == 2

    async def test_candidate_not_found(self, cand_repo: AsyncMock, run_repo: AsyncMock) -> None:
        cand_repo.get.return_value = None
        scheduler = PipelineScheduler(cand_repo, run_repo, {})

        jobs_added = await scheduler.load_schedules("candidate_1")

        assert jobs_added == 0

    async def test_skips_empty_schedules(
        self, cand_repo: AsyncMock, run_repo: AsyncMock
    ) -> None:
        candidate = Candidate(
            candidate_id="candidate_1",
            name="Test Candidate",
            schedules=ScheduleConfig(),
        )
        cand_repo.get.return_value = candidate

        scheduler = PipelineScheduler(cand_repo, run_repo, {})
        jobs_added = await scheduler.load_schedules("candidate_1")

        assert jobs_added == 0


class TestSchedulerExecuteStage:
    async def test_executes_and_logs_run(
        self, cand_repo: AsyncMock, run_repo: AsyncMock, mock_stage: AsyncMock
    ) -> None:
        stages = {"harvest": mock_stage}
        scheduler = PipelineScheduler(cand_repo, run_repo, stages)

        await scheduler._execute_stage("candidate_1", "harvest", TriggerType.SCHEDULED, "linkedin")

        run_repo.create.assert_called_once()
        mock_stage.run.assert_called_once_with("candidate_1")
        update_call = run_repo.update.call_args
        assert update_call[1]["status"].value == "completed"

    async def test_logs_failure(
        self, cand_repo: AsyncMock, run_repo: AsyncMock
    ) -> None:
        failing_stage = AsyncMock()
        failing_stage.run.side_effect = Exception("Boom")
        stages = {"harvest": failing_stage}
        scheduler = PipelineScheduler(cand_repo, run_repo, stages)

        await scheduler._execute_stage("candidate_1", "harvest", TriggerType.MANUAL)

        update_call = run_repo.update.call_args
        assert update_call[1]["status"].value == "failed"

    async def test_missing_stage(
        self, cand_repo: AsyncMock, run_repo: AsyncMock
    ) -> None:
        scheduler = PipelineScheduler(cand_repo, run_repo, {})

        await scheduler._execute_stage("candidate_1", "harvest", TriggerType.MANUAL)

        update_call = run_repo.update.call_args
        assert update_call[1]["status"].value == "failed"

    async def test_skipped_when_disabled(
        self, cand_repo: AsyncMock, run_repo: AsyncMock, mock_stage: AsyncMock
    ) -> None:
        stages = {"harvest": mock_stage}
        scheduler = PipelineScheduler(cand_repo, run_repo, stages)
        scheduler.enabled = False

        await scheduler._execute_stage("candidate_1", "harvest", TriggerType.SCHEDULED)

        run_repo.create.assert_called_once()
        created_run = run_repo.create.call_args[0][0]
        assert created_run.status == RunStatus.SKIPPED
        mock_stage.run.assert_not_called()


class TestSchedulerToggle:
    def test_default_enabled(self, cand_repo: AsyncMock, run_repo: AsyncMock) -> None:
        scheduler = PipelineScheduler(cand_repo, run_repo, {})
        assert scheduler.enabled is True

    def test_toggle_off_and_on(self, cand_repo: AsyncMock, run_repo: AsyncMock) -> None:
        scheduler = PipelineScheduler(cand_repo, run_repo, {})
        scheduler.enabled = False
        assert scheduler.enabled is False
        scheduler.enabled = True
        assert scheduler.enabled is True


class TestSchedulerManualTrigger:
    async def test_trigger_manual_returns_run_id(
        self, cand_repo: AsyncMock, run_repo: AsyncMock, mock_stage: AsyncMock
    ) -> None:
        stages = {"harvest": mock_stage}
        scheduler = PipelineScheduler(cand_repo, run_repo, stages)

        run_id = await scheduler.trigger_manual("candidate_1", "harvest")

        assert run_id == "run_1"
        run_repo.create.assert_called_once()

    async def test_trigger_manual_skipped_when_disabled(
        self, cand_repo: AsyncMock, run_repo: AsyncMock, mock_stage: AsyncMock
    ) -> None:
        stages = {"harvest": mock_stage}
        scheduler = PipelineScheduler(cand_repo, run_repo, stages)
        scheduler.enabled = False

        run_id = await scheduler.trigger_manual("candidate_1", "harvest")

        assert run_id == "run_1"
        created_run = run_repo.create.call_args[0][0]
        assert created_run.status == RunStatus.SKIPPED


class TestSchedulerLifecycle:
    async def test_start_stop(self, cand_repo: AsyncMock, run_repo: AsyncMock) -> None:
        scheduler = PipelineScheduler(cand_repo, run_repo, {})

        assert not scheduler.is_running
        scheduler.start()
        assert scheduler.is_running
        scheduler.stop()
        assert not scheduler.is_running

    def test_active_runs_empty(self, cand_repo: AsyncMock, run_repo: AsyncMock) -> None:
        scheduler = PipelineScheduler(cand_repo, run_repo, {})
        assert scheduler.get_active_runs() == []
