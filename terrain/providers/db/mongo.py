"""MongoDB adapter — repository implementations using motor async driver."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

from terrain.models.candidate import ActivePrompts, AIRoutingConfig, Candidate
from terrain.models.interesting_company import InterestingCompany
from terrain.models.opportunity import (
    Application,
    CoverLetter,
    DedupResult,
    Opportunity,
    OpportunityError,
    PipelineState,
    ScoringResult,
)
from terrain.models.pipeline import ApiUsage, PipelineRun
from terrain.providers.db.base import OpportunityFilters

logger = logging.getLogger(__name__)


def _to_oid(id_str: str) -> ObjectId:
    """Convert string ID to ObjectId."""
    return ObjectId(id_str)


def _from_doc(doc: dict[str, Any], model_class: type) -> Any:
    """Convert a MongoDB document to a Pydantic model."""
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return model_class.model_validate(doc)


class MongoOpportunityRepository:
    """MongoDB implementation of OpportunityRepository."""

    def __init__(self, collection: AsyncIOMotorCollection) -> None:
        self._col = collection

    async def create(self, opportunity: Opportunity) -> str:
        doc = opportunity.model_dump(by_alias=True, exclude={"id"})
        doc["updated_at"] = datetime.now(timezone.utc)
        result = await self._col.insert_one(doc)
        return str(result.inserted_id)

    async def get(self, candidate_id: str, opportunity_id: str) -> Optional[Opportunity]:
        doc = await self._col.find_one(
            {"_id": _to_oid(opportunity_id), "candidate_id": candidate_id}
        )
        return _from_doc(doc, Opportunity) if doc else None

    async def find_unscored(self, candidate_id: str) -> list[Opportunity]:
        cursor = self._col.find({
            "candidate_id": candidate_id,
            "pipeline_state": PipelineState.HARVESTED.value,
            "scoring": None,
        })
        return [_from_doc(doc, Opportunity) async for doc in cursor]

    async def find_by_company_title(
        self, candidate_id: str, company: str, title: str
    ) -> list[Opportunity]:
        cursor = self._col.find({
            "candidate_id": candidate_id,
            "company": company,
            "title": title,
        })
        return [_from_doc(doc, Opportunity) async for doc in cursor]

    async def find_awaiting_cover_letter(self, candidate_id: str) -> list[Opportunity]:
        cursor = self._col.find({
            "candidate_id": candidate_id,
            "pipeline_state": PipelineState.APPLIED.value,
            "application": {"$ne": None},
            "cover_letter": None,
        })
        return [_from_doc(doc, Opportunity) async for doc in cursor]

    async def find_for_ui(
        self, candidate_id: str, filters: OpportunityFilters
    ) -> list[Opportunity]:
        query: dict[str, Any] = {
            "candidate_id": candidate_id,
            "archived": filters.archived,
        }

        if filters.pipeline_state:
            query["pipeline_state"] = filters.pipeline_state.value
        if filters.recommendation:
            query["scoring.recommendation"] = filters.recommendation
        if filters.work_arrangement:
            query["scoring.work_arrangement"] = filters.work_arrangement
        if filters.company:
            query["company"] = {"$regex": filters.company, "$options": "i"}
        if filters.date_from:
            query.setdefault("created_at", {})["$gte"] = filters.date_from
        if filters.date_to:
            query.setdefault("created_at", {})["$lte"] = filters.date_to
        if filters.search_text:
            query["$or"] = [
                {"company": {"$regex": filters.search_text, "$options": "i"}},
                {"title": {"$regex": filters.search_text, "$options": "i"}},
            ]

        cursor = self._col.find(query).sort("created_at", -1)
        return [_from_doc(doc, Opportunity) async for doc in cursor]

    async def _update_subdoc(
        self, candidate_id: str, opp_id: str, field: str, data: dict[str, Any]
    ) -> None:
        await self._col.update_one(
            {"_id": _to_oid(opp_id), "candidate_id": candidate_id},
            {"$set": {field: data, "updated_at": datetime.now(timezone.utc)}},
        )

    async def update_scoring(
        self, candidate_id: str, opp_id: str, scoring: ScoringResult
    ) -> None:
        await self._update_subdoc(
            candidate_id, opp_id, "scoring", scoring.model_dump()
        )

    async def update_application(
        self, candidate_id: str, opp_id: str, application: Application
    ) -> None:
        await self._update_subdoc(
            candidate_id, opp_id, "application", application.model_dump()
        )

    async def update_cover_letter(
        self, candidate_id: str, opp_id: str, cover_letter: CoverLetter
    ) -> None:
        await self._update_subdoc(
            candidate_id, opp_id, "cover_letter", cover_letter.model_dump()
        )

    async def update_dedup(
        self, candidate_id: str, opp_id: str, dedup: DedupResult
    ) -> None:
        await self._update_subdoc(
            candidate_id, opp_id, "dedup", dedup.model_dump()
        )

    async def update_pipeline_state(
        self, candidate_id: str, opp_id: str, state: PipelineState
    ) -> None:
        await self._col.update_one(
            {"_id": _to_oid(opp_id), "candidate_id": candidate_id},
            {"$set": {"pipeline_state": state.value, "updated_at": datetime.now(timezone.utc)}},
        )

    async def add_error(
        self, candidate_id: str, opp_id: str, error: OpportunityError
    ) -> None:
        await self._col.update_one(
            {"_id": _to_oid(opp_id), "candidate_id": candidate_id},
            {
                "$push": {"errors": error.model_dump()},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )

    async def update_notes(self, candidate_id: str, opp_id: str, notes: str) -> None:
        await self._col.update_one(
            {"_id": _to_oid(opp_id), "candidate_id": candidate_id},
            {"$set": {"notes": notes, "updated_at": datetime.now(timezone.utc)}},
        )


class MongoCandidateRepository:
    """MongoDB implementation of CandidateRepository."""

    def __init__(self, collection: AsyncIOMotorCollection) -> None:
        self._col = collection

    async def get(self, candidate_id: str) -> Optional[Candidate]:
        doc = await self._col.find_one({"candidate_id": candidate_id})
        return _from_doc(doc, Candidate) if doc else None

    async def update_active_prompts(
        self, candidate_id: str, prompts: ActivePrompts
    ) -> None:
        await self._col.update_one(
            {"candidate_id": candidate_id},
            {"$set": {"active_prompts": prompts.model_dump()}},
        )

    async def get_ai_routing(self, candidate_id: str) -> Optional[AIRoutingConfig]:
        doc = await self._col.find_one(
            {"candidate_id": candidate_id}, {"ai_routing": 1}
        )
        if doc and doc.get("ai_routing"):
            return AIRoutingConfig.model_validate(doc["ai_routing"])
        return None


class MongoPipelineRunRepository:
    """MongoDB implementation of PipelineRunRepository."""

    def __init__(self, collection: AsyncIOMotorCollection) -> None:
        self._col = collection

    async def create(self, run: PipelineRun) -> str:
        doc = run.model_dump(by_alias=True, exclude={"id"})
        result = await self._col.insert_one(doc)
        return str(result.inserted_id)

    async def update(self, run_id: str, **fields: object) -> None:
        # Convert enums to values for MongoDB
        update_fields = {}
        for k, v in fields.items():
            if hasattr(v, "value"):
                update_fields[k] = v.value
            else:
                update_fields[k] = v
        await self._col.update_one(
            {"_id": _to_oid(run_id)},
            {"$set": update_fields},
        )

    async def get_latest(
        self, candidate_id: str, stage: str
    ) -> Optional[PipelineRun]:
        doc = await self._col.find_one(
            {"candidate_id": candidate_id, "stage": stage},
            sort=[("started_at", -1)],
        )
        return _from_doc(doc, PipelineRun) if doc else None

    async def find_by_candidate(
        self, candidate_id: str, limit: int = 50
    ) -> list[PipelineRun]:
        cursor = (
            self._col.find({"candidate_id": candidate_id})
            .sort("started_at", -1)
            .limit(limit)
        )
        return [_from_doc(doc, PipelineRun) async for doc in cursor]


class MongoApiUsageRepository:
    """MongoDB implementation of ApiUsageRepository."""

    def __init__(self, collection: AsyncIOMotorCollection) -> None:
        self._col = collection

    async def log(self, usage: ApiUsage) -> None:
        await self._col.insert_one(usage.model_dump())

    async def get_cost_summary(
        self, candidate_id: str, since: datetime
    ) -> dict[str, float]:
        pipeline = [
            {"$match": {"candidate_id": candidate_id, "timestamp": {"$gte": since}}},
            {"$group": {"_id": "$task", "total_cost": {"$sum": "$cost_usd"}}},
        ]
        result: dict[str, float] = {}
        async for doc in self._col.aggregate(pipeline):
            result[doc["_id"]] = doc["total_cost"]
        return result


class MongoInterestingCompanyRepository:
    """MongoDB implementation of InterestingCompanyRepository."""

    def __init__(self, collection: AsyncIOMotorCollection) -> None:
        self._col = collection

    async def create(self, company: InterestingCompany) -> str:
        doc = company.model_dump(by_alias=True, exclude={"id"})
        doc["updated_at"] = datetime.now(timezone.utc)
        result = await self._col.insert_one(doc)
        return str(result.inserted_id)

    async def find_by_candidate(self, candidate_id: str) -> list[InterestingCompany]:
        cursor = self._col.find({"candidate_id": candidate_id})
        return [_from_doc(doc, InterestingCompany) async for doc in cursor]

    async def find_by_name(
        self, candidate_id: str, company_name: str
    ) -> Optional[InterestingCompany]:
        doc = await self._col.find_one(
            {"candidate_id": candidate_id, "company_name": company_name}
        )
        return _from_doc(doc, InterestingCompany) if doc else None

    async def update(
        self, candidate_id: str, company_id: str, **fields: object
    ) -> None:
        update_fields = dict(fields)
        update_fields["updated_at"] = datetime.now(timezone.utc)
        await self._col.update_one(
            {"_id": _to_oid(company_id), "candidate_id": candidate_id},
            {"$set": update_fields},
        )

    async def delete(self, candidate_id: str, company_id: str) -> None:
        await self._col.delete_one(
            {"_id": _to_oid(company_id), "candidate_id": candidate_id}
        )


class MongoDatabaseClient:
    """MongoDB connection manager — owns the client and provides repository instances."""

    def __init__(self, mongo_uri: str) -> None:
        self._client = AsyncIOMotorClient(mongo_uri)
        self._db: AsyncIOMotorDatabase = self._client.get_default_database()

    @property
    def opportunities(self) -> MongoOpportunityRepository:
        return MongoOpportunityRepository(self._db["opportunities"])

    @property
    def candidates(self) -> MongoCandidateRepository:
        return MongoCandidateRepository(self._db["candidates"])

    @property
    def pipeline_runs(self) -> MongoPipelineRunRepository:
        return MongoPipelineRunRepository(self._db["pipeline_runs"])

    @property
    def api_usage(self) -> MongoApiUsageRepository:
        return MongoApiUsageRepository(self._db["api_usage"])

    @property
    def interesting_companies(self) -> MongoInterestingCompanyRepository:
        return MongoInterestingCompanyRepository(self._db["interesting_companies"])

    async def initialize(self) -> None:
        """Create indexes on all collections."""
        opps = self._db["opportunities"]
        await opps.create_index([("candidate_id", 1), ("pipeline_state", 1)])
        await opps.create_index([("candidate_id", 1), ("company", 1), ("title", 1)])
        await opps.create_index([("candidate_id", 1), ("scoring.recommendation", 1)])

        runs = self._db["pipeline_runs"]
        await runs.create_index([("candidate_id", 1), ("stage", 1), ("started_at", -1)])

        usage = self._db["api_usage"]
        await usage.create_index([("candidate_id", 1), ("timestamp", -1)])

        ics = self._db["interesting_companies"]
        await ics.create_index([("candidate_id", 1), ("company_name", 1)])

        cands = self._db["candidates"]
        await cands.create_index([("candidate_id", 1)], unique=True)

        logger.info("MongoDB indexes created")

    def close(self) -> None:
        """Close the MongoDB client."""
        self._client.close()
