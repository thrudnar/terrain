"""Opportunity API routes."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from terrain.models.opportunity import (
    ApplicationStatus,
    Opportunity,
    PipelineState,
    Source,
)
from terrain.providers.db.base import OpportunityFilters

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


class OpportunityListResponse(BaseModel):
    items: list[Opportunity]
    count: int


class NotesUpdate(BaseModel):
    notes: str


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus


class CreateOpportunityRequest(BaseModel):
    company: str
    title: str
    description_text: str
    location: Optional[str] = None
    work_type: Optional[str] = None
    url: Optional[str] = None


@router.get("", response_model=OpportunityListResponse)
async def list_opportunities(
    request: Request,
    candidate_id: str = Query(default="candidate_1"),
    pipeline_state: Optional[PipelineState] = None,
    recommendation: Optional[str] = None,
    work_arrangement: Optional[str] = None,
    company: Optional[str] = None,
    search_text: Optional[str] = None,
    archived: bool = False,
) -> OpportunityListResponse:
    filters = OpportunityFilters(
        pipeline_state=pipeline_state,
        recommendation=recommendation,
        work_arrangement=work_arrangement,
        company=company,
        search_text=search_text,
        archived=archived,
    )
    db = request.app.state.db
    items = await db.opportunities.find_for_ui(candidate_id, filters)
    return OpportunityListResponse(items=items, count=len(items))


@router.get("/{opportunity_id}", response_model=Opportunity)
async def get_opportunity(
    request: Request,
    opportunity_id: str,
    candidate_id: str = Query(default="candidate_1"),
) -> Opportunity:
    db = request.app.state.db
    opp = await db.opportunities.get(candidate_id, opportunity_id)
    if opp is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return opp


@router.patch("/{opportunity_id}/notes")
async def update_notes(
    request: Request,
    opportunity_id: str,
    body: NotesUpdate,
    candidate_id: str = Query(default="candidate_1"),
) -> dict[str, str]:
    db = request.app.state.db
    opp = await db.opportunities.get(candidate_id, opportunity_id)
    if opp is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    await db.opportunities.update_notes(candidate_id, opportunity_id, body.notes)
    return {"status": "updated"}


@router.patch("/{opportunity_id}/application")
async def update_application_status(
    request: Request,
    opportunity_id: str,
    body: ApplicationStatusUpdate,
    candidate_id: str = Query(default="candidate_1"),
) -> dict[str, str]:
    db = request.app.state.db
    opp = await db.opportunities.get(candidate_id, opportunity_id)
    if opp is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    if opp.application is None:
        raise HTTPException(status_code=400, detail="No application exists for this opportunity")
    opp.application.status = body.status
    await db.opportunities.update_application(candidate_id, opportunity_id, opp.application)
    return {"status": "updated"}


@router.post("", status_code=201)
async def create_opportunity(
    request: Request,
    body: CreateOpportunityRequest,
    candidate_id: str = Query(default="candidate_1"),
) -> dict[str, str]:
    db = request.app.state.db
    now = datetime.now(timezone.utc)
    opp = Opportunity(
        candidate_id=candidate_id,
        source=Source(
            board="manual",
            board_job_id="manual",
            collection="manual",
            url=body.url or "",
            first_seen=now,
            last_seen=now,
        ),
        company=body.company,
        title=body.title,
        description_text=body.description_text,
        location=body.location,
        work_type=body.work_type,
        pipeline_state=PipelineState.HARVESTED,
    )
    opp_id = await db.opportunities.create(opp)
    return {"id": opp_id}
