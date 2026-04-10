"""Candidate profile model — prompts, schedules, AI routing config."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ActivePrompts(BaseModel):
    scoring: str = "v1"
    cover_letter: str = "v1"
    dedup: str = "v1"


class PromptHistoryEntry(BaseModel):
    type: str
    version: str
    activated: datetime
    deactivated: Optional[datetime] = None


class ScheduleConfig(BaseModel):
    harvest_linkedin: Optional[str] = None
    harvest_jobright: Optional[str] = None
    score_batch: Optional[str] = None
    cover_letter_batch: Optional[str] = None


class AIRoutingEntry(BaseModel):
    provider: str
    model: str
    skill: Optional[str] = None


class AIRoutingConfig(BaseModel):
    scoring: AIRoutingEntry
    cover_letter: AIRoutingEntry
    dedup_similarity: AIRoutingEntry
    email_classification: Optional[AIRoutingEntry] = None


class Candidate(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    candidate_id: str
    name: str
    active_prompts: ActivePrompts = Field(default_factory=ActivePrompts)
    prompt_history: list[PromptHistoryEntry] = Field(default_factory=list)
    schedules: ScheduleConfig = Field(default_factory=ScheduleConfig)
    ai_routing: Optional[AIRoutingConfig] = None

    model_config = {"populate_by_name": True}
