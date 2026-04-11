"""Promoter stage — evaluates scored opportunities against thresholds and promotes to application."""

from datetime import datetime, timezone
from typing import Optional

from terrain.models.opportunity import Application, ApplicationStatus, PipelineState
from terrain.models.pipeline import PipelineStageEnum, StageResult
from terrain.providers.db.base import InterestingCompanyRepository, OpportunityRepository


class Promoter:
    """Promotes scored opportunities that meet configurable thresholds."""

    def __init__(
        self,
        opportunity_repo: OpportunityRepository,
        interesting_company_repo: InterestingCompanyRepository,
        threshold: int = 75,
        interesting_company_boost: int = 5,
    ) -> None:
        self._opp_repo = opportunity_repo
        self._ic_repo = interesting_company_repo
        self._threshold = threshold
        self._boost = interesting_company_boost

    async def run(
        self, candidate_id: str, options: Optional[dict[str, object]] = None
    ) -> StageResult:
        threshold = self._threshold
        if options and "threshold" in options:
            threshold = int(options["threshold"])

        scored = await self._opp_repo.find_unscored(candidate_id)
        # find_unscored returns harvested opps; we need scored ones instead.
        # We'll use find_for_ui with pipeline_state=scored.
        from terrain.providers.db.base import OpportunityFilters

        filters = OpportunityFilters(pipeline_state=PipelineState.SCORED)
        scored_opps = await self._opp_repo.find_for_ui(candidate_id, filters)

        promoted = 0
        errors: list[str] = []

        for opp in scored_opps:
            if opp.scoring is None:
                continue

            effective_threshold = threshold
            if opp.interesting_company_match:
                effective_threshold -= self._boost

            if opp.scoring.overall >= effective_threshold:
                try:
                    application = Application(
                        status=ApplicationStatus.NEW,
                        source=opp.application.source if opp.application else "harvested",
                    )
                    await self._opp_repo.update_application(
                        candidate_id, opp.id or "", application
                    )
                    await self._opp_repo.update_pipeline_state(
                        candidate_id, opp.id or "", PipelineState.APPLIED
                    )
                    promoted += 1
                except Exception as e:
                    errors.append(f"Failed to promote {opp.id}: {e}")

        return StageResult(
            stage=PipelineStageEnum.PROMOTION,
            items_processed=len(scored_opps),
            items_new=promoted,
            items_error=len(errors),
            errors=errors,
        )

    async def run_one(self, candidate_id: str, opportunity_id: str) -> StageResult:
        opp = await self._opp_repo.get(candidate_id, opportunity_id)
        if opp is None:
            return StageResult(
                stage=PipelineStageEnum.PROMOTION,
                items_error=1,
                errors=[f"Opportunity {opportunity_id} not found"],
            )

        if opp.scoring is None:
            return StageResult(
                stage=PipelineStageEnum.PROMOTION,
                items_error=1,
                errors=[f"Opportunity {opportunity_id} has no scoring"],
            )

        effective_threshold = self._threshold
        if opp.interesting_company_match:
            effective_threshold -= self._boost

        if opp.scoring.overall >= effective_threshold:
            application = Application(status=ApplicationStatus.NEW)
            await self._opp_repo.update_application(candidate_id, opportunity_id, application)
            await self._opp_repo.update_pipeline_state(
                candidate_id, opportunity_id, PipelineState.APPLIED
            )
            return StageResult(
                stage=PipelineStageEnum.PROMOTION,
                items_processed=1,
                items_new=1,
            )

        return StageResult(
            stage=PipelineStageEnum.PROMOTION,
            items_processed=1,
        )
