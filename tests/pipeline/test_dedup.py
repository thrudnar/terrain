"""Tests for the dedup pipeline stage."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from terrain.models.candidate import ActivePrompts, Candidate
from terrain.models.opportunity import (
    DedupMethod,
    DedupResult,
    DedupStatus,
    Opportunity,
    PipelineState,
    Source,
)
from terrain.models.pipeline import PipelineStageEnum
from terrain.pipeline.dedup import Dedup
from terrain.providers.ai.base import CompletionResponse


def _make_opp(opp_id: str = "opp1", company: str = "Acme", title: str = "Senior Data Engineer") -> Opportunity:
    return Opportunity(
        _id=opp_id,
        candidate_id="candidate_1",
        source=Source(
            board="linkedin",
            board_job_id=opp_id,
            collection="top-applicant",
            url=f"https://linkedin.com/jobs/view/{opp_id}",
            first_seen=datetime(2026, 4, 1, tzinfo=timezone.utc),
            last_seen=datetime(2026, 4, 1, tzinfo=timezone.utc),
        ),
        company=company,
        title=title,
        description_text=f"Job description for {opp_id}",
        pipeline_state=PipelineState.HARVESTED,
    )


def _make_candidate() -> Candidate:
    return Candidate(
        candidate_id="candidate_1",
        name="Test Candidate",
        active_prompts=ActivePrompts(dedup="v1"),
    )


def _similarity_response(classification: str, score: float) -> CompletionResponse:
    return CompletionResponse(
        content=json.dumps({
            "classification": classification,
            "similarity_score": score,
            "reasoning": "Test",
        }),
        model="llama3.1:8b-q4",
    )


@pytest.fixture
def prompt_dir(tmp_path: Path) -> Path:
    dedup_dir = tmp_path / "candidate_1" / "dedup"
    dedup_dir.mkdir(parents=True)
    (dedup_dir / "v1.md").write_text(
        "# Dedup\n\n## System Prompt\n\nCompare jobs.\n\n"
        "## Job A (existing)\n\n{description_a}\n\n## Job B (new)\n\n{description_b}"
    )
    return tmp_path


class TestDedupParseResponse:
    def test_parses_duplicate(self, prompt_dir: Path) -> None:
        dedup = Dedup(AsyncMock(), AsyncMock(), AsyncMock(), prompt_dir)
        status, score = dedup._parse_similarity_response(
            json.dumps({"classification": "duplicate", "similarity_score": 0.98})
        )
        assert status == DedupStatus.DUPLICATE
        assert score == 0.98

    def test_parses_repost_evolved(self, prompt_dir: Path) -> None:
        dedup = Dedup(AsyncMock(), AsyncMock(), AsyncMock(), prompt_dir)
        status, score = dedup._parse_similarity_response(
            json.dumps({"classification": "repost_evolved", "similarity_score": 0.7})
        )
        assert status == DedupStatus.REPOST_EVOLVED


class TestDedupRunOne:
    async def test_unique_no_matches(self, prompt_dir: Path) -> None:
        opp_repo = AsyncMock()
        cand_repo = AsyncMock()
        ai = AsyncMock()

        cand_repo.get.return_value = _make_candidate()
        opp_repo.get.return_value = _make_opp("new1")
        opp_repo.find_by_company_title.return_value = [_make_opp("new1")]  # only self

        dedup = Dedup(opp_repo, cand_repo, ai, prompt_dir)
        result = await dedup.run_one("candidate_1", "new1")

        assert result.items_new == 1
        call_args = opp_repo.update_dedup.call_args[0]
        dedup_result = call_args[2]
        assert dedup_result.status == DedupStatus.UNIQUE
        assert dedup_result.method == DedupMethod.EXACT

    async def test_duplicate_via_similarity(self, prompt_dir: Path) -> None:
        opp_repo = AsyncMock()
        cand_repo = AsyncMock()
        ai = AsyncMock()

        existing = _make_opp("existing1")
        new_opp = _make_opp("new1")

        cand_repo.get.return_value = _make_candidate()
        opp_repo.get.return_value = new_opp
        opp_repo.find_by_company_title.return_value = [new_opp, existing]
        ai.complete.return_value = _similarity_response("duplicate", 0.95)

        dedup = Dedup(opp_repo, cand_repo, ai, prompt_dir)
        result = await dedup.run_one("candidate_1", "new1")

        assert result.items_new == 0
        call_args = opp_repo.update_dedup.call_args[0]
        dedup_result = call_args[2]
        assert dedup_result.status == DedupStatus.DUPLICATE
        assert dedup_result.parent_id == "existing1"

    async def test_repost_evolved_treated_as_new(self, prompt_dir: Path) -> None:
        opp_repo = AsyncMock()
        cand_repo = AsyncMock()
        ai = AsyncMock()

        existing = _make_opp("existing1")
        new_opp = _make_opp("new1")

        cand_repo.get.return_value = _make_candidate()
        opp_repo.get.return_value = new_opp
        opp_repo.find_by_company_title.return_value = [new_opp, existing]
        ai.complete.return_value = _similarity_response("repost_evolved", 0.7)

        dedup = Dedup(opp_repo, cand_repo, ai, prompt_dir)
        result = await dedup.run_one("candidate_1", "new1")

        assert result.items_new == 1
        call_args = opp_repo.update_dedup.call_args[0]
        dedup_result = call_args[2]
        assert dedup_result.status == DedupStatus.REPOST_EVOLVED
        assert dedup_result.parent_id is None

    async def test_candidate_not_found(self, prompt_dir: Path) -> None:
        opp_repo = AsyncMock()
        cand_repo = AsyncMock()
        cand_repo.get.return_value = None

        dedup = Dedup(opp_repo, cand_repo, AsyncMock(), prompt_dir)
        result = await dedup.run_one("candidate_1", "opp1")

        assert result.items_error == 1
