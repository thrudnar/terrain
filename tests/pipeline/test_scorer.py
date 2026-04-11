"""Tests for the scorer pipeline stage."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from terrain.models.candidate import ActivePrompts, Candidate
from terrain.models.opportunity import (
    Opportunity,
    PipelineState,
    Recommendation,
    Source,
)
from terrain.models.pipeline import PipelineStageEnum
from terrain.pipeline.scorer import Scorer
from terrain.providers.ai.base import CompletionResponse


SAMPLE_SCORING_JSON = json.dumps(
    {
        "reasoning": "Strong match across all dimensions.",
        "overall": 82,
        "skills": 85,
        "seniority": 80,
        "work_type": 90,
        "work_arrangement": "Remote",
        "salary_range": "Not stated",
        "match_summary": "Clean structural match. Tim's org-building experience maps directly.",
        "strengths": ["org-building", "data platform", "regulated industry"],
        "gaps": ["unfamiliar domain"],
        "recommendation": "STRONG FIT",
    }
)


def _make_opp(opp_id: str = "opp1") -> Opportunity:
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
        description_text="We are looking for a VP of Data...",
        pipeline_state=PipelineState.HARVESTED,
    )


def _make_candidate() -> Candidate:
    return Candidate(
        candidate_id="candidate_1",
        name="Test Candidate",
        active_prompts=ActivePrompts(scoring="v1"),
    )


@pytest.fixture
def opp_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def cand_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def ai_provider() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def prompt_dir(tmp_path: Path) -> Path:
    scoring_dir = tmp_path / "candidate_1" / "scoring"
    scoring_dir.mkdir(parents=True)
    prompt_content = """# Score Prompt v1

## System Prompt

You are a job fit evaluator.

## User Prompt Template

Evaluate this job:

<job_description>
{description_text}
</job_description>

## Notes

Test prompt.
"""
    (scoring_dir / "v1.md").write_text(prompt_content)
    return tmp_path


class TestScorerParseResponse:
    def test_parses_valid_json(self, prompt_dir: Path) -> None:
        scorer = Scorer(AsyncMock(), AsyncMock(), AsyncMock(), prompt_dir)
        result = scorer._parse_scoring_response(SAMPLE_SCORING_JSON, "v1", "claude-sonnet-4-6")

        assert result.overall == 82
        assert result.skills == 85
        assert result.recommendation == Recommendation.STRONG_FIT
        assert result.strengths == ["org-building", "data platform", "regulated industry"]
        assert result.gaps == ["unfamiliar domain"]
        assert result.prompt_version == "v1"
        assert result.model == "claude-sonnet-4-6"

    def test_strips_markdown_code_fences(self, prompt_dir: Path) -> None:
        scorer = Scorer(AsyncMock(), AsyncMock(), AsyncMock(), prompt_dir)
        wrapped = f"```json\n{SAMPLE_SCORING_JSON}\n```"
        result = scorer._parse_scoring_response(wrapped, "v1", "test-model")

        assert result.overall == 82

    def test_invalid_json_raises(self, prompt_dir: Path) -> None:
        scorer = Scorer(AsyncMock(), AsyncMock(), AsyncMock(), prompt_dir)
        with pytest.raises(Exception):
            scorer._parse_scoring_response("not json", "v1", "test")


class TestScorerLoadPrompt:
    def test_loads_and_splits_prompt(self, prompt_dir: Path) -> None:
        scorer = Scorer(AsyncMock(), AsyncMock(), AsyncMock(), prompt_dir)
        system, user = scorer._load_prompt("candidate_1", "v1")

        assert "job fit evaluator" in system
        assert "{description_text}" in user
        assert "## Notes" not in user


class TestScorerRun:
    async def test_scores_unscored_opportunities(
        self,
        opp_repo: AsyncMock,
        cand_repo: AsyncMock,
        ai_provider: AsyncMock,
        prompt_dir: Path,
    ) -> None:
        cand_repo.get.return_value = _make_candidate()
        opp_repo.find_unscored.return_value = [_make_opp()]
        ai_provider.complete.return_value = CompletionResponse(
            content=SAMPLE_SCORING_JSON,
            input_tokens=1000,
            output_tokens=200,
            model="claude-sonnet-4-6",
        )

        scorer = Scorer(opp_repo, cand_repo, ai_provider, prompt_dir)
        result = await scorer.run("candidate_1")

        assert result.stage == PipelineStageEnum.SCORING
        assert result.items_new == 1
        assert result.items_error == 0
        opp_repo.update_scoring.assert_called_once()
        opp_repo.update_pipeline_state.assert_called_once()

    async def test_handles_ai_error(
        self,
        opp_repo: AsyncMock,
        cand_repo: AsyncMock,
        ai_provider: AsyncMock,
        prompt_dir: Path,
    ) -> None:
        cand_repo.get.return_value = _make_candidate()
        opp_repo.find_unscored.return_value = [_make_opp()]
        ai_provider.complete.side_effect = Exception("API error")

        scorer = Scorer(opp_repo, cand_repo, ai_provider, prompt_dir)
        result = await scorer.run("candidate_1")

        assert result.items_error == 1
        assert result.items_new == 0

    async def test_candidate_not_found(
        self, opp_repo: AsyncMock, cand_repo: AsyncMock, ai_provider: AsyncMock, prompt_dir: Path
    ) -> None:
        cand_repo.get.return_value = None

        scorer = Scorer(opp_repo, cand_repo, ai_provider, prompt_dir)
        result = await scorer.run("candidate_1")

        assert result.items_error == 1

    async def test_uses_cache_control(
        self,
        opp_repo: AsyncMock,
        cand_repo: AsyncMock,
        ai_provider: AsyncMock,
        prompt_dir: Path,
    ) -> None:
        cand_repo.get.return_value = _make_candidate()
        opp_repo.find_unscored.return_value = [_make_opp()]
        ai_provider.complete.return_value = CompletionResponse(
            content=SAMPLE_SCORING_JSON, model="claude-sonnet-4-6"
        )

        scorer = Scorer(opp_repo, cand_repo, ai_provider, prompt_dir)
        await scorer.run("candidate_1")

        call_args = ai_provider.complete.call_args[0][0]
        assert call_args.cache_control is True


class TestScorerRunOne:
    async def test_scores_single(
        self,
        opp_repo: AsyncMock,
        cand_repo: AsyncMock,
        ai_provider: AsyncMock,
        prompt_dir: Path,
    ) -> None:
        cand_repo.get.return_value = _make_candidate()
        opp_repo.get.return_value = _make_opp()
        ai_provider.complete.return_value = CompletionResponse(
            content=SAMPLE_SCORING_JSON, model="claude-sonnet-4-6"
        )

        scorer = Scorer(opp_repo, cand_repo, ai_provider, prompt_dir)
        result = await scorer.run_one("candidate_1", "opp1")

        assert result.items_new == 1

    async def test_opportunity_not_found(
        self, opp_repo: AsyncMock, cand_repo: AsyncMock, ai_provider: AsyncMock, prompt_dir: Path
    ) -> None:
        cand_repo.get.return_value = _make_candidate()
        opp_repo.get.return_value = None

        scorer = Scorer(opp_repo, cand_repo, ai_provider, prompt_dir)
        result = await scorer.run_one("candidate_1", "opp1")

        assert result.items_error == 1
