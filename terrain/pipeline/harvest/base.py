"""Harvest source interface — the contract for LinkedIn, Jobright, etc."""

from typing import Optional, Protocol

from pydantic import BaseModel, Field


class RawOpportunity(BaseModel):
    """Pre-validation model with raw harvested fields."""

    board: str
    board_job_id: str
    collection: str
    url: str
    company: str
    title: str
    location: Optional[str] = None
    work_type: Optional[str] = None
    description_text: str
    posted_date: Optional[str] = None


class SourceConfig(BaseModel):
    """Configuration for a harvest source."""

    board: str
    collections: list[str] = Field(default_factory=list)
    base_url: Optional[str] = None
    max_pages: int = 10
    metadata: dict[str, str] = Field(default_factory=dict)


class HarvestSource(Protocol):
    """Interface for job board scrapers."""

    async def harvest(self, config: SourceConfig) -> list[RawOpportunity]: ...

    async def harvest_collection(
        self, config: SourceConfig, collection: str
    ) -> list[RawOpportunity]: ...
