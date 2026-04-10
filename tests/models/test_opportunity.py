"""Tests for opportunity data models."""

from datetime import datetime, timezone

import pytest

from terrain.models.opportunity import (
    Application,
    ApplicationStatus,
    CoverLetter,
    DedupMethod,
    DedupResult,
    DedupStatus,
    ErrorType,
    GenerationMethod,
    GmailEvent,
    Opportunity,
    OpportunityError,
    PipelineState,
    Recommendation,
    ScoringResult,
    Source,
)


def _make_source(**overrides: object) -> Source:
    defaults = {
        "board": "linkedin",
        "board_job_id": "123456",
        "collection": "top-applicant",
        "url": "https://linkedin.com/jobs/view/123456",
        "first_seen": datetime(2026, 4, 1, tzinfo=timezone.utc),
        "last_seen": datetime(2026, 4, 8, tzinfo=timezone.utc),
    }
    return Source(**(defaults | overrides))


def _make_opportunity(**overrides: object) -> Opportunity:
    defaults = {
        "candidate_id": "candidate_1",
        "source": _make_source(),
        "company": "Acme Corp",
        "title": "Senior Data Engineer",
        "description_text": "Full job description here.",
    }
    return Opportunity(**(defaults | overrides))


class TestSource:
    def test_required_fields(self) -> None:
        s = _make_source()
        assert s.board == "linkedin"
        assert s.posted_date is None

    def test_optional_posted_date(self) -> None:
        s = _make_source(posted_date=datetime(2026, 3, 28, tzinfo=timezone.utc))
        assert s.posted_date is not None


class TestOpportunity:
    def test_minimal_creation(self) -> None:
        opp = _make_opportunity()
        assert opp.candidate_id == "candidate_1"
        assert opp.pipeline_state == PipelineState.HARVESTED
        assert opp.archived is False
        assert opp.scoring is None
        assert opp.application is None
        assert opp.cover_letter is None
        assert opp.dedup is None
        assert opp.gmail_events == []
        assert opp.errors == []

    def test_timestamps_auto_set(self) -> None:
        opp = _make_opportunity()
        assert isinstance(opp.created_at, datetime)
        assert isinstance(opp.updated_at, datetime)

    def test_pipeline_state_enum(self) -> None:
        for state in PipelineState:
            opp = _make_opportunity(pipeline_state=state)
            assert opp.pipeline_state == state

    def test_invalid_pipeline_state_rejected(self) -> None:
        with pytest.raises(ValueError):
            _make_opportunity(pipeline_state="invalid_state")


class TestScoringResult:
    def test_creation(self) -> None:
        scoring = ScoringResult(
            prompt_version="v2",
            model="claude-haiku-4-5-20251001",
            overall=82,
            skills=85,
            seniority=80,
            work_type=90,
            match_summary="Strong match for senior data role.",
            strengths=["leadership", "analytics"],
            gaps=["industry experience"],
            recommendation=Recommendation.STRONG_FIT,
            reasoning="Solid fit overall.",
            scored_at=datetime(2026, 4, 2, tzinfo=timezone.utc),
        )
        assert scoring.overall == 82
        assert scoring.recommendation == Recommendation.STRONG_FIT

    def test_invalid_recommendation(self) -> None:
        with pytest.raises(ValueError):
            ScoringResult(
                prompt_version="v1",
                model="test",
                overall=50,
                skills=50,
                seniority=50,
                work_type=50,
                match_summary="test",
                recommendation="NOT_A_TIER",
                reasoning="test",
                scored_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            )


class TestDedupResult:
    def test_unique(self) -> None:
        d = DedupResult(
            status=DedupStatus.UNIQUE,
            checked_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            method=DedupMethod.EXACT,
        )
        assert d.parent_id is None
        assert d.similarity_score is None

    def test_duplicate_with_parent(self) -> None:
        d = DedupResult(
            status=DedupStatus.DUPLICATE,
            parent_id="abc123",
            checked_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            method=DedupMethod.SIMILARITY,
            similarity_score=0.94,
        )
        assert d.parent_id == "abc123"


class TestApplication:
    def test_defaults(self) -> None:
        app = Application()
        assert app.status == ApplicationStatus.NEW
        assert app.applied_date is None


class TestCoverLetter:
    def test_creation(self) -> None:
        cl = CoverLetter(
            prompt_version="v1",
            model="claude-sonnet-4-6",
            content="Dear Hiring Manager...",
            generated_at=datetime(2026, 4, 3, tzinfo=timezone.utc),
            skill_used="voice-of-tim",
            generation_method=GenerationMethod.REALTIME,
        )
        assert cl.skill_used == "voice-of-tim"


class TestOpportunityError:
    def test_creation(self) -> None:
        err = OpportunityError(
            stage="scoring",
            occurred_at=datetime(2026, 4, 8, tzinfo=timezone.utc),
            error_type=ErrorType.PARSE_ERROR,
            message="JSON parse failed",
            retryable=True,
        )
        assert err.retryable is True
        assert err.resolved_at is None


class TestGmailEvent:
    def test_creation(self) -> None:
        evt = GmailEvent(
            gmail_message_id="msg_abc",
            subject="Interview Scheduling",
            received_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
            characterization="interview_request",
        )
        assert evt.characterization == "interview_request"
