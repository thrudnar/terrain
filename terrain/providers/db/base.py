"""Database repository interfaces — the contract for MongoDB adapters."""

from datetime import datetime
from typing import Optional, Protocol

from pydantic import BaseModel, Field

from terrain.models.candidate import ActivePrompts, AIRoutingConfig, Candidate
from terrain.models.interesting_company import InterestingCompany
from terrain.models.opportunity import (
    Application,
    CoverLetter,
    DedupResult,
    OpportunityError,
    Opportunity,
    PipelineState,
    ScoringResult,
)
from terrain.models.pipeline import ApiUsage, PipelineRun


class OpportunityFilters(BaseModel):
    pipeline_state: Optional[PipelineState] = None
    recommendation: Optional[str] = None
    work_arrangement: Optional[str] = None
    company: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    search_text: Optional[str] = None
    archived: bool = False


class OpportunityRepository(Protocol):
    """All opportunity data access goes through here."""

    async def create(self, opportunity: Opportunity) -> str: ...

    async def get(self, candidate_id: str, opportunity_id: str) -> Optional[Opportunity]: ...

    async def find_unscored(self, candidate_id: str) -> list[Opportunity]: ...

    async def find_by_company_title(
        self, candidate_id: str, company: str, title: str
    ) -> list[Opportunity]: ...

    async def find_awaiting_cover_letter(self, candidate_id: str) -> list[Opportunity]: ...

    async def find_for_ui(
        self, candidate_id: str, filters: OpportunityFilters
    ) -> list[Opportunity]: ...

    async def update_scoring(
        self, candidate_id: str, opp_id: str, scoring: ScoringResult
    ) -> None: ...

    async def update_application(
        self, candidate_id: str, opp_id: str, application: Application
    ) -> None: ...

    async def update_cover_letter(
        self, candidate_id: str, opp_id: str, cover_letter: CoverLetter
    ) -> None: ...

    async def update_dedup(
        self, candidate_id: str, opp_id: str, dedup: DedupResult
    ) -> None: ...

    async def update_pipeline_state(
        self, candidate_id: str, opp_id: str, state: PipelineState
    ) -> None: ...

    async def add_error(
        self, candidate_id: str, opp_id: str, error: OpportunityError
    ) -> None: ...

    async def update_notes(self, candidate_id: str, opp_id: str, notes: str) -> None: ...


class CandidateRepository(Protocol):
    """Candidate profile data access."""

    async def get(self, candidate_id: str) -> Optional[Candidate]: ...

    async def update_active_prompts(
        self, candidate_id: str, prompts: ActivePrompts
    ) -> None: ...

    async def get_ai_routing(self, candidate_id: str) -> Optional[AIRoutingConfig]: ...


class PipelineRunRepository(Protocol):
    """Pipeline run tracking data access."""

    async def create(self, run: PipelineRun) -> str: ...

    async def update(self, run_id: str, **fields: object) -> None: ...

    async def get_latest(
        self, candidate_id: str, stage: str
    ) -> Optional[PipelineRun]: ...

    async def find_by_candidate(
        self, candidate_id: str, limit: int = 50
    ) -> list[PipelineRun]: ...


class ApiUsageRepository(Protocol):
    """API cost tracking data access."""

    async def log(self, usage: ApiUsage) -> None: ...

    async def get_cost_summary(
        self, candidate_id: str, since: datetime
    ) -> dict[str, float]: ...


class InterestingCompanyRepository(Protocol):
    """Interesting company watch list data access."""

    async def create(self, company: InterestingCompany) -> str: ...

    async def find_by_candidate(self, candidate_id: str) -> list[InterestingCompany]: ...

    async def find_by_name(
        self, candidate_id: str, company_name: str
    ) -> Optional[InterestingCompany]: ...

    async def update(self, candidate_id: str, company_id: str, **fields: object) -> None: ...

    async def delete(self, candidate_id: str, company_id: str) -> None: ...
