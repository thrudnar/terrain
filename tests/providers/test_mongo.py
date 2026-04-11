"""Tests for the MongoDB adapter — mocks motor collections."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from terrain.models.candidate import ActivePrompts, Candidate
from terrain.models.opportunity import (
    Application,
    Opportunity,
    PipelineState,
    ScoringResult,
    Recommendation,
    Source,
)
from terrain.models.pipeline import ApiUsage, PipelineRun, PipelineStageEnum
from terrain.providers.db.base import OpportunityFilters
from terrain.providers.db.mongo import (
    MongoCandidateRepository,
    MongoDatabaseClient,
    MongoOpportunityRepository,
    MongoPipelineRunRepository,
    MongoApiUsageRepository,
    MongoInterestingCompanyRepository,
)


OPP_OID = ObjectId()
OPP_ID = str(OPP_OID)


def _opp_doc() -> dict:
    return {
        "_id": OPP_OID,
        "candidate_id": "candidate_1",
        "source": {
            "board": "linkedin",
            "board_job_id": "123",
            "collection": "top-applicant",
            "url": "https://linkedin.com/jobs/view/123",
            "first_seen": datetime(2026, 4, 1, tzinfo=timezone.utc),
            "last_seen": datetime(2026, 4, 1, tzinfo=timezone.utc),
        },
        "company": "Acme Corp",
        "title": "Senior Data Engineer",
        "description_text": "Build the data org.",
        "pipeline_state": "harvested",
        "archived": False,
        "created_at": datetime(2026, 4, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 4, 1, tzinfo=timezone.utc),
        "scoring": None,
        "application": None,
        "cover_letter": None,
        "dedup": None,
        "notes": None,
        "gmail_events": [],
        "interesting_company_match": False,
        "errors": [],
    }


@pytest.fixture
def mock_collection() -> AsyncMock:
    col = AsyncMock()
    return col


class TestOpportunityRepository:
    async def test_create_returns_id(self, mock_collection: AsyncMock) -> None:
        mock_collection.insert_one.return_value = MagicMock(inserted_id=OPP_OID)
        repo = MongoOpportunityRepository(mock_collection)

        opp = Opportunity(
            candidate_id="candidate_1",
            source=Source(
                board="linkedin",
                board_job_id="123",
                collection="test",
                url="https://test.com",
                first_seen=datetime(2026, 4, 1, tzinfo=timezone.utc),
                last_seen=datetime(2026, 4, 1, tzinfo=timezone.utc),
            ),
            company="Acme",
            title="VP",
            description_text="Test",
        )
        result = await repo.create(opp)

        assert result == OPP_ID
        mock_collection.insert_one.assert_called_once()

    async def test_get_returns_opportunity(self, mock_collection: AsyncMock) -> None:
        mock_collection.find_one.return_value = _opp_doc()
        repo = MongoOpportunityRepository(mock_collection)

        opp = await repo.get("candidate_1", OPP_ID)

        assert opp is not None
        assert opp.company == "Acme Corp"
        assert opp.id == OPP_ID

    async def test_get_returns_none(self, mock_collection: AsyncMock) -> None:
        mock_collection.find_one.return_value = None
        repo = MongoOpportunityRepository(mock_collection)

        opp = await repo.get("candidate_1", OPP_ID)
        assert opp is None

    async def test_find_unscored_query(self, mock_collection: AsyncMock) -> None:
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = MagicMock(return_value=AsyncMock(__anext__=AsyncMock(side_effect=StopAsyncIteration)))
        # motor's find() is synchronous, returning a cursor
        mock_collection.find = MagicMock(return_value=mock_cursor)
        repo = MongoOpportunityRepository(mock_collection)

        await repo.find_unscored("candidate_1")

        query = mock_collection.find.call_args[0][0]
        assert query["candidate_id"] == "candidate_1"
        assert query["pipeline_state"] == "harvested"
        assert query["scoring"] is None

    async def test_update_scoring_stamps_updated_at(self, mock_collection: AsyncMock) -> None:
        repo = MongoOpportunityRepository(mock_collection)

        scoring = ScoringResult(
            prompt_version="v1",
            model="test",
            overall=80,
            skills=80,
            seniority=80,
            work_type=80,
            match_summary="Test",
            recommendation=Recommendation.STRONG_FIT,
            reasoning="Test",
            scored_at=datetime(2026, 4, 2, tzinfo=timezone.utc),
        )
        await repo.update_scoring("candidate_1", OPP_ID, scoring)

        call_args = mock_collection.update_one.call_args
        update_doc = call_args[0][1]
        assert "updated_at" in update_doc["$set"]

    async def test_find_for_ui_with_filters(self, mock_collection: AsyncMock) -> None:
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = MagicMock(return_value=AsyncMock(__anext__=AsyncMock(side_effect=StopAsyncIteration)))
        mock_cursor.sort.return_value = mock_cursor
        # motor's find() is synchronous
        mock_collection.find = MagicMock(return_value=mock_cursor)
        repo = MongoOpportunityRepository(mock_collection)

        filters = OpportunityFilters(
            pipeline_state=PipelineState.SCORED,
            company="Acme",
        )
        await repo.find_for_ui("candidate_1", filters)

        query = mock_collection.find.call_args[0][0]
        assert query["pipeline_state"] == "scored"
        assert query["company"]["$regex"] == "Acme"


class TestCandidateRepository:
    async def test_get(self, mock_collection: AsyncMock) -> None:
        mock_collection.find_one.return_value = {
            "_id": ObjectId(),
            "candidate_id": "candidate_1",
            "name": "Test Candidate",
            "active_prompts": {"scoring": "v1", "cover_letter": "v1", "dedup": "v1"},
            "prompt_history": [],
            "schedules": {},
        }
        repo = MongoCandidateRepository(mock_collection)

        cand = await repo.get("candidate_1")
        assert cand is not None
        assert cand.name == "Test Candidate"


class TestPipelineRunRepository:
    async def test_create(self, mock_collection: AsyncMock) -> None:
        mock_collection.insert_one.return_value = MagicMock(inserted_id=ObjectId())
        repo = MongoPipelineRunRepository(mock_collection)

        run = PipelineRun(candidate_id="candidate_1", stage=PipelineStageEnum.SCORING)
        result = await repo.create(run)

        assert isinstance(result, str)
        mock_collection.insert_one.assert_called_once()


class TestApiUsageRepository:
    async def test_log(self, mock_collection: AsyncMock) -> None:
        repo = MongoApiUsageRepository(mock_collection)
        usage = ApiUsage(
            provider="anthropic",
            model="claude-sonnet-4-6",
            task="scoring",
            candidate_id="candidate_1",
            input_tokens=1000,
            output_tokens=200,
            cost_usd=0.006,
        )
        await repo.log(usage)
        mock_collection.insert_one.assert_called_once()


class TestDatabaseClientIndexes:
    async def test_initialize_creates_indexes(self) -> None:
        with patch("terrain.providers.db.mongo.AsyncIOMotorClient") as mock_client_cls:
            mock_db = MagicMock()
            mock_collections: dict[str, AsyncMock] = {}

            def get_col(name: str) -> AsyncMock:
                if name not in mock_collections:
                    mock_collections[name] = AsyncMock()
                return mock_collections[name]

            mock_db.__getitem__ = lambda self, name: get_col(name)
            mock_client_cls.return_value.get_default_database.return_value = mock_db

            client = MongoDatabaseClient("mongodb://localhost:27017/terrain")
            await client.initialize()

            # Verify indexes were created on key collections
            assert mock_collections["opportunities"].create_index.call_count == 3
            assert mock_collections["pipeline_runs"].create_index.call_count == 1
            assert mock_collections["api_usage"].create_index.call_count == 1
            assert mock_collections["candidates"].create_index.call_count == 1
