"""Tests for the promoter pipeline stage."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from terrain.models.opportunity import (
    Application,
    ApplicationStatus,
    Opportunity,
    PipelineState,
    Recommendation,
    ScoringResult,
    Source,
)
from terrain.pipeline.promoter import Promoter


def _make_scored_opp(
    overall: int = 80,
    opp_id: str = "opp1",
    interesting: bool = False,
) -> Opportunity:
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
        description_text="Job description",
        pipeline_state=PipelineState.SCORED,
        interesting_company_match=interesting,
        scoring=ScoringResult(
            prompt_version="v1",
            model="claude-sonnet-4-6",
            overall=overall,
            skills=80,
            seniority=80,
            work_type=80,
            match_summary="Good match",
            recommendation=Recommendation.STRONG_FIT if overall >= 75 else Recommendation.GOOD_FIT,
            reasoning="Test",
            scored_at=datetime(2026, 4, 2, tzinfo=timezone.utc),
        ),
    )


@pytest.fixture
def opp_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def ic_repo() -> AsyncMock:
    return AsyncMock()


class TestPromoterRun:
    async def test_promotes_above_threshold(self, opp_repo: AsyncMock, ic_repo: AsyncMock) -> None:
        opp_repo.find_for_ui.return_value = [_make_scored_opp(overall=80)]
        promoter = Promoter(opp_repo, ic_repo, threshold=75)

        result = await promoter.run("candidate_1")

        assert result.items_new == 1
        opp_repo.update_application.assert_called_once()
        opp_repo.update_pipeline_state.assert_called_once()

    async def test_skips_below_threshold(self, opp_repo: AsyncMock, ic_repo: AsyncMock) -> None:
        opp_repo.find_for_ui.return_value = [_make_scored_opp(overall=60)]
        promoter = Promoter(opp_repo, ic_repo, threshold=75)

        result = await promoter.run("candidate_1")

        assert result.items_new == 0
        opp_repo.update_application.assert_not_called()

    async def test_boundary_score_equals_threshold(
        self, opp_repo: AsyncMock, ic_repo: AsyncMock
    ) -> None:
        opp_repo.find_for_ui.return_value = [_make_scored_opp(overall=75)]
        promoter = Promoter(opp_repo, ic_repo, threshold=75)

        result = await promoter.run("candidate_1")

        assert result.items_new == 1

    async def test_interesting_company_boost(
        self, opp_repo: AsyncMock, ic_repo: AsyncMock
    ) -> None:
        # Score 72 is below 75 threshold, but with 5-point boost, effective threshold is 70
        opp_repo.find_for_ui.return_value = [
            _make_scored_opp(overall=72, interesting=True)
        ]
        promoter = Promoter(opp_repo, ic_repo, threshold=75, interesting_company_boost=5)

        result = await promoter.run("candidate_1")

        assert result.items_new == 1

    async def test_interesting_company_still_below_boosted_threshold(
        self, opp_repo: AsyncMock, ic_repo: AsyncMock
    ) -> None:
        opp_repo.find_for_ui.return_value = [
            _make_scored_opp(overall=68, interesting=True)
        ]
        promoter = Promoter(opp_repo, ic_repo, threshold=75, interesting_company_boost=5)

        result = await promoter.run("candidate_1")

        assert result.items_new == 0

    async def test_custom_threshold_via_options(
        self, opp_repo: AsyncMock, ic_repo: AsyncMock
    ) -> None:
        opp_repo.find_for_ui.return_value = [_make_scored_opp(overall=60)]
        promoter = Promoter(opp_repo, ic_repo, threshold=75)

        result = await promoter.run("candidate_1", options={"threshold": 55})

        assert result.items_new == 1

    async def test_no_scored_opportunities(
        self, opp_repo: AsyncMock, ic_repo: AsyncMock
    ) -> None:
        opp_repo.find_for_ui.return_value = []
        promoter = Promoter(opp_repo, ic_repo)

        result = await promoter.run("candidate_1")

        assert result.items_processed == 0
        assert result.items_new == 0


class TestPromoterRunOne:
    async def test_promotes_single(self, opp_repo: AsyncMock, ic_repo: AsyncMock) -> None:
        opp_repo.get.return_value = _make_scored_opp(overall=80)
        promoter = Promoter(opp_repo, ic_repo, threshold=75)

        result = await promoter.run_one("candidate_1", "opp1")

        assert result.items_new == 1

    async def test_not_found(self, opp_repo: AsyncMock, ic_repo: AsyncMock) -> None:
        opp_repo.get.return_value = None
        promoter = Promoter(opp_repo, ic_repo)

        result = await promoter.run_one("candidate_1", "opp1")

        assert result.items_error == 1

    async def test_no_scoring(self, opp_repo: AsyncMock, ic_repo: AsyncMock) -> None:
        opp = _make_scored_opp(overall=80)
        opp.scoring = None
        opp_repo.get.return_value = opp
        promoter = Promoter(opp_repo, ic_repo)

        result = await promoter.run_one("candidate_1", "opp1")

        assert result.items_error == 1

    async def test_below_threshold(self, opp_repo: AsyncMock, ic_repo: AsyncMock) -> None:
        opp_repo.get.return_value = _make_scored_opp(overall=50)
        promoter = Promoter(opp_repo, ic_repo, threshold=75)

        result = await promoter.run_one("candidate_1", "opp1")

        assert result.items_new == 0
        assert result.items_processed == 1
