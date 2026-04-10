"""Pipeline run and API usage tracking models."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PipelineStageEnum(StrEnum):
    HARVEST = "harvest"
    DEDUP = "dedup"
    SCORING = "scoring"
    PROMOTION = "promotion"
    COVER_LETTER = "cover_letter"


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TriggerType(StrEnum):
    SCHEDULED = "scheduled"
    MANUAL = "manual"


class PipelineRun(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    candidate_id: str
    stage: PipelineStageEnum
    source: Optional[str] = None
    started_at: datetime = Field(default_factory=_utcnow)
    completed_at: Optional[datetime] = None
    trigger: TriggerType = TriggerType.MANUAL
    items_processed: int = 0
    items_new: int = 0
    items_duplicate: int = 0
    items_error: int = 0
    prompt_version: Optional[str] = None
    batch_id: Optional[str] = None
    cost_usd: float = 0.0
    error_log: list[str] = Field(default_factory=list)
    status: RunStatus = RunStatus.RUNNING

    model_config = {"populate_by_name": True}


class ApiUsage(BaseModel):
    provider: str
    model: str
    task: str
    candidate_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float = 0.0
    pipeline_run_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=_utcnow)


class StageResult(BaseModel):
    stage: PipelineStageEnum
    items_processed: int = 0
    items_new: int = 0
    items_error: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
