"""Tests for candidate data models."""

from datetime import datetime, timezone

from terrain.models.candidate import (
    ActivePrompts,
    AIRoutingConfig,
    AIRoutingEntry,
    Candidate,
    PromptHistoryEntry,
    ScheduleConfig,
)


class TestActivePrompts:
    def test_defaults(self) -> None:
        ap = ActivePrompts()
        assert ap.scoring == "v1"
        assert ap.cover_letter == "v1"
        assert ap.dedup == "v1"

    def test_override(self) -> None:
        ap = ActivePrompts(scoring="v3")
        assert ap.scoring == "v3"


class TestAIRoutingConfig:
    def test_full_config(self) -> None:
        config = AIRoutingConfig(
            scoring=AIRoutingEntry(provider="anthropic", model="claude-haiku-4-5-20251001"),
            cover_letter=AIRoutingEntry(
                provider="anthropic", model="claude-sonnet-4-6", skill="voice-of-tim"
            ),
            dedup_similarity=AIRoutingEntry(provider="ollama", model="llama3.1:8b-q4"),
        )
        assert config.scoring.provider == "anthropic"
        assert config.cover_letter.skill == "voice-of-tim"
        assert config.email_classification is None


class TestCandidate:
    def test_minimal(self) -> None:
        c = Candidate(candidate_id="candidate_1", name="Test Candidate")
        assert c.candidate_id == "candidate_1"
        assert c.active_prompts.scoring == "v1"
        assert c.prompt_history == []
        assert c.ai_routing is None

    def test_with_schedules(self) -> None:
        c = Candidate(
            candidate_id="candidate_1",
            name="Test Candidate",
            schedules=ScheduleConfig(
                harvest_linkedin="0 8,20 * * *",
                score_batch="0 10,22 * * *",
            ),
        )
        assert c.schedules.harvest_linkedin == "0 8,20 * * *"
        assert c.schedules.harvest_jobright is None

    def test_prompt_history(self) -> None:
        entry = PromptHistoryEntry(
            type="scoring",
            version="v1",
            activated=datetime(2026, 3, 15, tzinfo=timezone.utc),
        )
        c = Candidate(
            candidate_id="candidate_1",
            name="Test Candidate",
            prompt_history=[entry],
        )
        assert len(c.prompt_history) == 1
        assert c.prompt_history[0].deactivated is None
