"""Tests for the cover letter pipeline stage."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from terrain.models.candidate import (
    AIRoutingConfig,
    AIRoutingEntry,
    ActivePrompts,
    Candidate,
)
from terrain.models.opportunity import (
    Application,
    GenerationMethod,
    Opportunity,
    PipelineState,
    Recommendation,
    ScoringResult,
    Source,
)
from terrain.models.pipeline import PipelineStageEnum
from terrain.pipeline.cover_letter import CoverLetterGenerator
from terrain.providers.ai.base import CompletionResponse


def _make_opp_with_scoring(opp_id: str = "opp1") -> Opportunity:
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
        description_text="We need a VP of Data to build our data org from scratch.",
        pipeline_state=PipelineState.APPLIED,
        application=Application(),
        scoring=ScoringResult(
            prompt_version="v1",
            model="claude-sonnet-4-6",
            overall=85,
            skills=85,
            seniority=90,
            work_type=90,
            match_summary="Strong structural match. Org-building mandate maps directly.",
            strengths=["org-building", "data platform", "regulated industry"],
            gaps=["unfamiliar domain"],
            recommendation=Recommendation.STRONG_FIT,
            reasoning="Clean fit.",
            scored_at=datetime(2026, 4, 2, tzinfo=timezone.utc),
        ),
    )


def _make_candidate(skill: str | None = "voice-of-tim") -> Candidate:
    return Candidate(
        candidate_id="candidate_1",
        name="Test Candidate",
        active_prompts=ActivePrompts(cover_letter="v1"),
        ai_routing=AIRoutingConfig(
            scoring=AIRoutingEntry(provider="anthropic", model="claude-haiku-4-5-20251001"),
            cover_letter=AIRoutingEntry(
                provider="anthropic", model="claude-sonnet-4-6", skill=skill
            ),
            dedup_similarity=AIRoutingEntry(provider="ollama", model="llama3.1:8b-q4"),
        ),
    )


@pytest.fixture
def prompt_dir(tmp_path: Path) -> Path:
    cl_dir = tmp_path / "candidate_1" / "cover-letter"
    cl_dir.mkdir(parents=True)
    (cl_dir / "v1.md").write_text(
        "# Cover Letter v1\n\n## System Prompt\n\nWrite a cover letter.\n\n"
        "## User Prompt Template\n\n"
        "Company: {company}\nTitle: {title}\n\n{description_text}\n\n"
        "Match: {match_summary}\nStrengths: {strengths}\n\n"
        "Write the cover letter body now.\n\n"
        "## Notes\n\nTest."
    )
    return tmp_path


class TestCoverLetterRunOne:
    async def test_generates_cover_letter(self, prompt_dir: Path) -> None:
        opp_repo = AsyncMock()
        cand_repo = AsyncMock()
        ai = AsyncMock()

        cand_repo.get.return_value = _make_candidate()
        opp_repo.get.return_value = _make_opp_with_scoring()
        ai.complete.return_value = CompletionResponse(
            content="The opportunity to build Acme Corp's data organization...",
            model="claude-sonnet-4-6",
        )

        gen = CoverLetterGenerator(opp_repo, cand_repo, ai, prompt_dir)
        result = await gen.run_one("candidate_1", "opp1")

        assert result.items_new == 1
        opp_repo.update_cover_letter.assert_called_once()
        cover_letter = opp_repo.update_cover_letter.call_args[0][2]
        assert "Acme Corp" in cover_letter.content
        assert cover_letter.skill_used == "voice-of-tim"
        assert cover_letter.generation_method == GenerationMethod.REALTIME

    async def test_skill_fallback(self, prompt_dir: Path) -> None:
        opp_repo = AsyncMock()
        cand_repo = AsyncMock()
        ai = AsyncMock()

        cand_repo.get.return_value = _make_candidate()
        opp_repo.get.return_value = _make_opp_with_scoring()
        # First call with skill fails, second without skill succeeds
        ai.complete.side_effect = [
            Exception("Skill unavailable"),
            CompletionResponse(content="Fallback content", model="claude-sonnet-4-6"),
        ]

        gen = CoverLetterGenerator(opp_repo, cand_repo, ai, prompt_dir)
        result = await gen.run_one("candidate_1", "opp1")

        assert result.items_new == 1
        cover_letter = opp_repo.update_cover_letter.call_args[0][2]
        assert cover_letter.skill_used is None
        assert cover_letter.content == "Fallback content"

    async def test_template_substitution(self, prompt_dir: Path) -> None:
        opp_repo = AsyncMock()
        cand_repo = AsyncMock()
        ai = AsyncMock()

        cand_repo.get.return_value = _make_candidate()
        opp_repo.get.return_value = _make_opp_with_scoring()
        ai.complete.return_value = CompletionResponse(content="Letter", model="test")

        gen = CoverLetterGenerator(opp_repo, cand_repo, ai, prompt_dir)
        await gen.run_one("candidate_1", "opp1")

        call_request = ai.complete.call_args[0][0]
        assert "Acme Corp" in call_request.user_prompt
        assert "Senior Data Engineer" in call_request.user_prompt
        assert "org-building" in call_request.user_prompt

    async def test_candidate_not_found(self, prompt_dir: Path) -> None:
        opp_repo = AsyncMock()
        cand_repo = AsyncMock()
        cand_repo.get.return_value = None

        gen = CoverLetterGenerator(opp_repo, cand_repo, AsyncMock(), prompt_dir)
        result = await gen.run_one("candidate_1", "opp1")

        assert result.items_error == 1


class TestCoverLetterRun:
    async def test_generates_batch(self, prompt_dir: Path) -> None:
        opp_repo = AsyncMock()
        cand_repo = AsyncMock()
        ai = AsyncMock()

        cand_repo.get.return_value = _make_candidate()
        opp_repo.find_awaiting_cover_letter.return_value = [
            _make_opp_with_scoring("opp1"),
            _make_opp_with_scoring("opp2"),
        ]
        ai.complete.return_value = CompletionResponse(content="Letter", model="test")

        gen = CoverLetterGenerator(opp_repo, cand_repo, ai, prompt_dir)
        result = await gen.run("candidate_1")

        assert result.items_new == 2
        assert result.stage == PipelineStageEnum.COVER_LETTER

    async def test_handles_error_in_batch(self, prompt_dir: Path) -> None:
        opp_repo = AsyncMock()
        cand_repo = AsyncMock()
        ai = AsyncMock()

        cand_repo.get.return_value = _make_candidate(skill=None)
        opp_repo.find_awaiting_cover_letter.return_value = [_make_opp_with_scoring()]
        ai.complete.side_effect = Exception("API down")

        gen = CoverLetterGenerator(opp_repo, cand_repo, ai, prompt_dir)
        result = await gen.run("candidate_1")

        assert result.items_error == 1
        assert result.items_new == 0
