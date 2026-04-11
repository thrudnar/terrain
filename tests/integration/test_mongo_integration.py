"""Integration tests for MongoDB — requires a running MongoDB instance.

Run with: pytest tests/integration/test_mongo_integration.py -v
Requires: docker compose up -d
"""

from datetime import datetime, timezone

import pytest

from terrain.models.candidate import ActivePrompts, Candidate
from terrain.models.interesting_company import InterestingCompany
from terrain.models.opportunity import (
    Application,
    Opportunity,
    PipelineState,
    Recommendation,
    ScoringResult,
    Source,
)
from terrain.models.pipeline import ApiUsage, PipelineRun, PipelineStageEnum
from terrain.providers.db.base import OpportunityFilters
from terrain.providers.db.mongo import MongoDatabaseClient

TEST_DB_URI = "mongodb://localhost:27017/terrain_test"


@pytest.fixture
async def db():
    """Create a fresh test database, yield client, then drop."""
    client = MongoDatabaseClient(TEST_DB_URI)
    await client.initialize()
    yield client
    # Clean up
    await client._db.drop_collection("opportunities")
    await client._db.drop_collection("candidates")
    await client._db.drop_collection("pipeline_runs")
    await client._db.drop_collection("api_usage")
    await client._db.drop_collection("interesting_companies")
    client.close()


def _make_opp(company: str = "Acme Corp", title: str = "Senior Data Engineer") -> Opportunity:
    now = datetime.now(timezone.utc)
    return Opportunity(
        candidate_id="candidate_1",
        source=Source(
            board="linkedin",
            board_job_id="12345",
            collection="top-applicant",
            url="https://linkedin.com/jobs/view/12345",
            first_seen=now,
            last_seen=now,
        ),
        company=company,
        title=title,
        description_text="Build and lead the data organization.",
        pipeline_state=PipelineState.HARVESTED,
    )


@pytest.mark.integration
class TestOpportunityCRUD:
    async def test_create_and_get(self, db: MongoDatabaseClient) -> None:
        opp = _make_opp()
        opp_id = await db.opportunities.create(opp)

        assert opp_id is not None
        retrieved = await db.opportunities.get("candidate_1", opp_id)
        assert retrieved is not None
        assert retrieved.company == "Acme Corp"
        assert retrieved.id == opp_id

    async def test_find_unscored(self, db: MongoDatabaseClient) -> None:
        opp = _make_opp()
        await db.opportunities.create(opp)

        unscored = await db.opportunities.find_unscored("candidate_1")
        assert len(unscored) == 1
        assert unscored[0].company == "Acme Corp"

    async def test_update_scoring(self, db: MongoDatabaseClient) -> None:
        opp = _make_opp()
        opp_id = await db.opportunities.create(opp)

        scoring = ScoringResult(
            prompt_version="v1",
            model="claude-sonnet-4-6",
            overall=85,
            skills=85,
            seniority=90,
            work_type=90,
            match_summary="Strong match.",
            strengths=["org-building", "data platform"],
            gaps=["unfamiliar domain"],
            recommendation=Recommendation.STRONG_FIT,
            reasoning="Clean fit.",
            scored_at=datetime.now(timezone.utc),
        )
        await db.opportunities.update_scoring("candidate_1", opp_id, scoring)
        await db.opportunities.update_pipeline_state("candidate_1", opp_id, PipelineState.SCORED)

        updated = await db.opportunities.get("candidate_1", opp_id)
        assert updated.scoring is not None
        assert updated.scoring.overall == 85
        assert updated.pipeline_state == PipelineState.SCORED

    async def test_find_for_ui_with_filters(self, db: MongoDatabaseClient) -> None:
        await db.opportunities.create(_make_opp("Acme Corp", "Senior Data Engineer"))
        await db.opportunities.create(_make_opp("Beta Inc", "Analytics Manager"))

        filters = OpportunityFilters(company="Acme")
        results = await db.opportunities.find_for_ui("candidate_1", filters)
        assert len(results) == 1
        assert results[0].company == "Acme Corp"

    async def test_find_by_company_title(self, db: MongoDatabaseClient) -> None:
        await db.opportunities.create(_make_opp("Acme Corp", "Senior Data Engineer"))
        await db.opportunities.create(_make_opp("Acme Corp", "Senior Data Engineer"))

        matches = await db.opportunities.find_by_company_title("candidate_1", "Acme Corp", "Senior Data Engineer")
        assert len(matches) == 2

    async def test_update_notes(self, db: MongoDatabaseClient) -> None:
        opp_id = await db.opportunities.create(_make_opp())
        await db.opportunities.update_notes("candidate_1", opp_id, "Recruiter call 4/5")

        updated = await db.opportunities.get("candidate_1", opp_id)
        assert updated.notes == "Recruiter call 4/5"


@pytest.mark.integration
class TestCandidateCRUD:
    async def test_seed_and_get(self, db: MongoDatabaseClient) -> None:
        await db._db["candidates"].insert_one({
            "candidate_id": "candidate_1",
            "name": "Test Candidate",
            "active_prompts": {"scoring": "v1", "cover_letter": "v1", "dedup": "v1"},
            "prompt_history": [],
            "schedules": {},
        })

        cand = await db.candidates.get("candidate_1")
        assert cand is not None
        assert cand.name == "Test Candidate"
        assert cand.active_prompts.scoring == "v1"


@pytest.mark.integration
class TestPipelineRunCRUD:
    async def test_create_and_get_latest(self, db: MongoDatabaseClient) -> None:
        run = PipelineRun(
            candidate_id="candidate_1",
            stage=PipelineStageEnum.SCORING,
        )
        run_id = await db.pipeline_runs.create(run)
        assert run_id is not None

        latest = await db.pipeline_runs.get_latest("candidate_1", "scoring")
        assert latest is not None


@pytest.mark.integration
class TestApiUsage:
    async def test_log_and_summarize(self, db: MongoDatabaseClient) -> None:
        usage = ApiUsage(
            provider="anthropic",
            model="claude-sonnet-4-6",
            task="scoring",
            candidate_id="candidate_1",
            input_tokens=1000,
            output_tokens=200,
            cost_usd=0.006,
        )
        await db.api_usage.log(usage)

        from datetime import timedelta
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        summary = await db.api_usage.get_cost_summary("candidate_1", since)
        assert "scoring" in summary
        assert summary["scoring"] == 0.006
