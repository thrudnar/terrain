"""Harvest stage adapter — bridges HarvestSource to PipelineStage interface."""

import hashlib
import time
from datetime import datetime, timezone
from typing import Optional

from terrain.models.opportunity import Opportunity, PipelineState, Source
from terrain.models.pipeline import PipelineStageEnum, StageResult
from terrain.pipeline.harvest.base import HarvestSource, RawOpportunity, SourceConfig
from terrain.providers.db.base import CandidateRepository, OpportunityRepository


class HarvestStage:
    """Adapts a HarvestSource into the PipelineStage interface.

    Requires a valid candidate — the LinkedIn session belongs to a specific candidate,
    and all harvested opportunities are scoped to that candidate_id.
    """

    def __init__(
        self,
        source: HarvestSource,
        opportunity_repo: OpportunityRepository,
        candidate_repo: CandidateRepository,
        config: SourceConfig,
    ) -> None:
        self._source = source
        self._opp_repo = opportunity_repo
        self._cand_repo = candidate_repo
        self._config = config

    async def _insert_if_new(
        self, candidate_id: str, raw: RawOpportunity
    ) -> bool:
        """Insert a harvested opportunity if it doesn't already exist. Returns True if new."""
        existing = await self._opp_repo.find_by_company_title(
            candidate_id, raw.company, raw.title
        )
        for opp in existing:
            if opp.source.board_job_id == raw.board_job_id:
                return False

        now = datetime.now(timezone.utc)
        desc = raw.description_text or ""
        opp = Opportunity(
            candidate_id=candidate_id,
            source=Source(
                board=raw.board,
                board_job_id=raw.board_job_id,
                collection=raw.collection,
                url=raw.url,
                first_seen=now,
                last_seen=now,
                posted_date=None,
            ),
            company=raw.company,
            title=raw.title,
            location=raw.location,
            work_type=raw.work_type,
            description_text=desc,
            description_hash=f"sha256:{hashlib.sha256(desc.encode()).hexdigest()[:16]}",
            pipeline_state=PipelineState.HARVESTED,
        )
        await self._opp_repo.create(opp)
        return True

    async def run(
        self, candidate_id: str, options: Optional[dict[str, object]] = None
    ) -> StageResult:
        start = time.monotonic()
        errors: list[str] = []

        # Validate candidate exists — the LinkedIn session is candidate-specific
        candidate = await self._cand_repo.get(candidate_id)
        if candidate is None:
            return StageResult(
                stage=PipelineStageEnum.HARVEST,
                items_error=1,
                errors=[f"Candidate {candidate_id} not found"],
                duration_seconds=time.monotonic() - start,
            )

        try:
            raw_opps = await self._source.harvest(self._config)
        except Exception as e:
            return StageResult(
                stage=PipelineStageEnum.HARVEST,
                items_error=1,
                errors=[f"Harvest failed: {e}"],
                duration_seconds=time.monotonic() - start,
            )

        new_count = 0
        for raw in raw_opps:
            try:
                is_new = await self._insert_if_new(candidate_id, raw)
                if is_new:
                    new_count += 1
            except Exception as e:
                errors.append(f"Failed to insert {raw.board_job_id}: {e}")

        return StageResult(
            stage=PipelineStageEnum.HARVEST,
            items_processed=len(raw_opps),
            items_new=new_count,
            items_error=len(errors),
            errors=errors,
            duration_seconds=time.monotonic() - start,
        )

    async def run_one(self, candidate_id: str, opportunity_id: str) -> StageResult:
        """Not applicable for harvest — harvest operates on collections, not single opportunities."""
        return StageResult(
            stage=PipelineStageEnum.HARVEST,
            items_error=1,
            errors=["Harvest does not support run_one — use run() to harvest collections"],
        )
