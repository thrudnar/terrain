"""Pipeline stage interface — the contract for all pipeline stages."""

from typing import Optional, Protocol

from terrain.models.pipeline import StageResult


class PipelineStage(Protocol):
    """Interface for pipeline stages: harvest, dedup, score, promote, cover letter."""

    async def run(
        self, candidate_id: str, options: Optional[dict[str, object]] = None
    ) -> StageResult: ...

    async def run_one(self, candidate_id: str, opportunity_id: str) -> StageResult: ...
