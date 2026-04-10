"""Interesting company model — per-candidate watch list."""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InterestingCompany(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    candidate_id: str
    company_name: str
    interest_drivers: list[str] = Field(default_factory=list)
    apprehensions: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    model_config = {"populate_by_name": True}
