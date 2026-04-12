"""End-to-end smoke test — walks a synthetic opportunity through the full pipeline.

Run with: pytest tests/integration/test_e2e.py -v
Requires: docker compose up -d (MongoDB)
Uses mocked AI providers (no real Anthropic/Ollama calls).
"""

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
from terrain.pipeline.cover_letter import CoverLetterGenerator
from terrain.pipeline.dedup import Dedup
from terrain.pipeline.promoter import Promoter
from terrain.pipeline.scorer import Scorer
from terrain.providers.ai.base import CompletionResponse
from terrain.providers.db.mongo import MongoDatabaseClient

TEST_DB_URI = "mongodb://localhost:27017/terrain_test_e2e"

MOCK_SCORE_RESPONSE = json.dumps({
    "reasoning": "Clean structural match across dimensions.",
    "overall": 85,
    "skills": 85,
    "seniority": 90,
    "work_type": 90,
    "work_arrangement": "Remote",
    "salary_range": "Not stated",
    "match_summary": "Strong org-building match. Experience maps directly.",
    "strengths": ["org-building", "data platform", "regulated industry"],
    "gaps": ["unfamiliar domain"],
    "recommendation": "STRONG FIT",
})


@pytest.fixture
async def db():
    client = MongoDatabaseClient(TEST_DB_URI)
    await client.initialize()
    yield client
    await client._db.drop_collection("opportunities")
    await client._db.drop_collection("candidates")
    await client._db.drop_collection("pipeline_runs")
    await client._db.drop_collection("api_usage")
    await client._db.drop_collection("interesting_companies")
    client.close()


@pytest.fixture
def prompt_dir(tmp_path: Path) -> Path:
    """Create temporary prompt files for testing."""
    scoring_dir = tmp_path / "candidate_1" / "scoring"
    scoring_dir.mkdir(parents=True)
    (scoring_dir / "v1.md").write_text(
        "# Scoring\n\n## System Prompt\n\nEvaluate job fit.\n\n"
        "## User Prompt Template\n\nEvaluate:\n\n{description_text}\n\n## Notes\n\nTest."
    )

    dedup_dir = tmp_path / "candidate_1" / "dedup"
    dedup_dir.mkdir(parents=True)
    (dedup_dir / "v1.md").write_text(
        "# Dedup\n\n## System Prompt\n\nCompare jobs.\n\n"
        "## Job A (existing)\n\n{description_a}\n\n## Job B (new)\n\n{description_b}"
    )

    cl_dir = tmp_path / "candidate_1" / "cover-letter"
    cl_dir.mkdir(parents=True)
    (cl_dir / "v1.md").write_text(
        "# Cover Letter\n\n## System Prompt\n\nWrite a letter.\n\n"
        "## User Prompt Template\n\nCompany: {company}\nTitle: {title}\n\n"
        "{description_text}\n\nMatch: {match_summary}\nStrengths: {strengths}\n\n"
        "Write now.\n\n## Notes\n\nTest."
    )

    return tmp_path


@pytest.mark.integration
class TestEndToEnd:
    async def test_full_pipeline_walk(
        self, db: MongoDatabaseClient, prompt_dir: Path
    ) -> None:
        """Walk a synthetic opportunity through: insert → dedup → score → promote → cover letter."""

        # === Seed candidate ===
        await db._db["candidates"].insert_one({
            "candidate_id": "candidate_1",
            "name": "Test Candidate",
            "active_prompts": {"scoring": "v1", "cover_letter": "v1", "dedup": "v1"},
            "prompt_history": [],
            "schedules": {},
        })

        # === Step 1: Insert opportunity ===
        now = datetime.now(timezone.utc)
        opp = Opportunity(
            candidate_id="candidate_1",
            source=Source(
                board="linkedin",
                board_job_id="99999",
                collection="top-applicant",
                url="https://linkedin.com/jobs/view/99999",
                first_seen=now,
                last_seen=now,
            ),
            company="E2E Test Corp",
            title="Senior Data Engineer",
            description_text="Build our data organization from scratch. Remote. Greenfield charter.",
            pipeline_state=PipelineState.HARVESTED,
        )
        opp_id = await db.opportunities.create(opp)
        assert opp_id is not None

        # === Step 2: Dedup (should mark unique — no collisions) ===
        mock_ai = AsyncMock()
        dedup = Dedup(db.opportunities, db.candidates, mock_ai, prompt_dir)
        result = await dedup.run_one("candidate_1", opp_id)
        assert result.items_new == 1  # unique

        opp_after_dedup = await db.opportunities.get("candidate_1", opp_id)
        assert opp_after_dedup.dedup is not None
        assert opp_after_dedup.dedup.status.value == "unique"

        # === Step 3: Score (mocked AI returns known JSON) ===
        mock_ai.complete.return_value = CompletionResponse(
            content=MOCK_SCORE_RESPONSE,
            input_tokens=2000,
            output_tokens=300,
            model="claude-sonnet-4-6",
        )
        scorer = Scorer(db.opportunities, db.candidates, mock_ai, prompt_dir)
        result = await scorer.run_one("candidate_1", opp_id)
        assert result.items_new == 1

        opp_after_score = await db.opportunities.get("candidate_1", opp_id)
        assert opp_after_score.scoring is not None
        assert opp_after_score.scoring.overall == 85
        assert opp_after_score.scoring.recommendation == Recommendation.STRONG_FIT
        assert opp_after_score.pipeline_state == PipelineState.SCORED

        # === Step 4: Promote (score 85 >= threshold 75) ===
        promoter = Promoter(db.opportunities, db.interesting_companies, threshold=75)
        result = await promoter.run_one("candidate_1", opp_id)
        assert result.items_new == 1

        opp_after_promote = await db.opportunities.get("candidate_1", opp_id)
        assert opp_after_promote.application is not None
        assert opp_after_promote.pipeline_state == PipelineState.APPLIED

        # === Step 5: Cover letter (mocked AI) ===
        mock_ai.complete.return_value = CompletionResponse(
            content="The opportunity to build E2E Test Corp's data organization from the ground up is exactly the kind of challenge I've spent my career pursuing.",
            model="claude-sonnet-4-6",
        )
        cover_gen = CoverLetterGenerator(db.opportunities, db.candidates, mock_ai, prompt_dir)
        result = await cover_gen.run_one("candidate_1", opp_id)
        assert result.items_new == 1

        # === Final verification: fully populated document ===
        final = await db.opportunities.get("candidate_1", opp_id)
        assert final is not None
        assert final.source.board_job_id == "99999"
        assert final.dedup is not None
        assert final.scoring is not None
        assert final.scoring.overall == 85
        assert final.application is not None
        assert final.cover_letter is not None
        assert "E2E Test Corp" in final.cover_letter.content
        assert final.pipeline_state == PipelineState.APPLIED
        assert final.company == "E2E Test Corp"
