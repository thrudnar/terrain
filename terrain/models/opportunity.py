"""Opportunity document model — the core data structure of the pipeline."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field


class DedupStatus(StrEnum):
    UNIQUE = "unique"
    DUPLICATE = "duplicate"
    REPOST_UNCHANGED = "repost_unchanged"
    REPOST_EVOLVED = "repost_evolved"


class DedupMethod(StrEnum):
    EXACT = "exact"
    SIMILARITY = "similarity"


class Recommendation(StrEnum):
    STRONG_FIT = "STRONG FIT"
    GOOD_FIT = "GOOD FIT"
    MARGINAL_FIT = "MARGINAL FIT"
    SKIP = "SKIP"


class ApplicationStatus(StrEnum):
    NEW = "new"
    APPLIED = "applied"
    WAITING = "waiting"
    PHONE_SCREEN = "phone_screen"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    DEAD = "dead"


class ApplicationSource(StrEnum):
    HARVESTED = "harvested"
    MANUAL = "manual"


class GenerationMethod(StrEnum):
    BATCH = "batch"
    REALTIME = "realtime"


class PipelineState(StrEnum):
    HARVESTED = "harvested"
    SCORED = "scored"
    APPLIED = "applied"
    ACTIVE = "active"
    CLOSED = "closed"


class ErrorType(StrEnum):
    RATE_LIMIT = "rate_limit"
    API_ERROR = "api_error"
    PARSE_ERROR = "parse_error"
    TIMEOUT = "timeout"
    VALIDATION = "validation"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Source(BaseModel):
    board: str
    board_job_id: str
    collection: str
    url: str
    first_seen: datetime
    last_seen: datetime
    posted_date: Optional[datetime] = None


class DedupResult(BaseModel):
    status: DedupStatus
    parent_id: Optional[str] = None
    checked_at: datetime
    method: DedupMethod
    similarity_score: Optional[float] = None


class ScoringResult(BaseModel):
    prompt_version: str
    model: str
    overall: int
    skills: int
    seniority: int
    work_type: int
    work_arrangement: Optional[str] = None
    salary_range: Optional[str] = None
    match_summary: str
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    recommendation: Recommendation
    reasoning: str
    scored_at: datetime


class Application(BaseModel):
    status: ApplicationStatus = ApplicationStatus.NEW
    applied_date: Optional[datetime] = None
    application_link: Optional[str] = None
    contact: Optional[str] = None
    resume_version: Optional[str] = None
    source: ApplicationSource = ApplicationSource.HARVESTED


class CoverLetter(BaseModel):
    prompt_version: str
    model: str
    content: str
    generated_at: datetime
    skill_used: Optional[str] = None
    generation_method: GenerationMethod


class GmailEvent(BaseModel):
    gmail_message_id: str
    subject: str
    received_at: datetime
    characterization: str


class OpportunityError(BaseModel):
    stage: str
    occurred_at: datetime
    run_id: Optional[str] = None
    error_type: ErrorType
    message: str
    retryable: bool = False
    resolved_at: Optional[datetime] = None


class Opportunity(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    candidate_id: str
    source: Source
    company: str
    title: str
    location: Optional[str] = None
    work_type: Optional[str] = None
    description_text: str
    description_hash: Optional[str] = None

    dedup: Optional[DedupResult] = None
    scoring: Optional[ScoringResult] = None
    application: Optional[Application] = None
    cover_letter: Optional[CoverLetter] = None
    notes: Optional[str] = None
    gmail_events: list[GmailEvent] = Field(default_factory=list)
    interesting_company_match: bool = False
    errors: list[OpportunityError] = Field(default_factory=list)

    pipeline_state: PipelineState = PipelineState.HARVESTED
    archived: bool = False
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    model_config = {"populate_by_name": True}
