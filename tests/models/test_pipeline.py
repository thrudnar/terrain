"""Tests for pipeline run and API usage models."""

from datetime import datetime, timezone

from terrain.models.pipeline import (
    ApiUsage,
    PipelineRun,
    PipelineStageEnum,
    RunStatus,
    StageResult,
    TriggerType,
)


class TestPipelineRun:
    def test_defaults(self) -> None:
        run = PipelineRun(
            candidate_id="candidate_1",
            stage=PipelineStageEnum.SCORING,
        )
        assert run.status == RunStatus.RUNNING
        assert run.trigger == TriggerType.MANUAL
        assert run.items_processed == 0
        assert run.cost_usd == 0.0
        assert run.error_log == []
        assert run.completed_at is None

    def test_completed_run(self) -> None:
        run = PipelineRun(
            candidate_id="candidate_1",
            stage=PipelineStageEnum.HARVEST,
            source="linkedin",
            trigger=TriggerType.SCHEDULED,
            items_processed=47,
            items_new=12,
            items_duplicate=3,
            status=RunStatus.COMPLETED,
            completed_at=datetime(2026, 4, 8, 8, 3, 42, tzinfo=timezone.utc),
        )
        assert run.items_new == 12
        assert run.status == RunStatus.COMPLETED


class TestApiUsage:
    def test_creation(self) -> None:
        usage = ApiUsage(
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
            task="scoring",
            candidate_id="candidate_1",
            input_tokens=4200,
            output_tokens=800,
            cached_tokens=3800,
            cost_usd=0.0012,
        )
        assert usage.cost_usd == 0.0012
        assert isinstance(usage.timestamp, datetime)


class TestStageResult:
    def test_defaults(self) -> None:
        result = StageResult(stage=PipelineStageEnum.DEDUP)
        assert result.items_processed == 0
        assert result.errors == []
        assert result.duration_seconds == 0.0

    def test_with_errors(self) -> None:
        result = StageResult(
            stage=PipelineStageEnum.SCORING,
            items_processed=10,
            items_error=2,
            errors=["rate limit on item 3", "parse error on item 7"],
            duration_seconds=45.2,
        )
        assert len(result.errors) == 2
