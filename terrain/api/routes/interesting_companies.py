"""Interesting companies API routes."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from terrain.models.interesting_company import InterestingCompany

router = APIRouter(prefix="/api/interesting-companies", tags=["interesting-companies"])


class InterestingCompanyListResponse(BaseModel):
    items: list[InterestingCompany]
    count: int


class CreateInterestingCompanyRequest(BaseModel):
    company_name: str
    interest_drivers: list[str] = []
    apprehensions: list[str] = []
    notes: Optional[str] = None


class UpdateInterestingCompanyRequest(BaseModel):
    interest_drivers: Optional[list[str]] = None
    apprehensions: Optional[list[str]] = None
    notes: Optional[str] = None


@router.get("", response_model=InterestingCompanyListResponse)
async def list_interesting_companies(
    request: Request,
    candidate_id: str = Query(default="candidate_1"),
) -> InterestingCompanyListResponse:
    db = request.app.state.db
    items = await db.interesting_companies.find_by_candidate(candidate_id)
    return InterestingCompanyListResponse(items=items, count=len(items))


@router.post("", status_code=201)
async def create_interesting_company(
    request: Request,
    body: CreateInterestingCompanyRequest,
    candidate_id: str = Query(default="candidate_1"),
) -> dict[str, str]:
    db = request.app.state.db
    company = InterestingCompany(
        candidate_id=candidate_id,
        company_name=body.company_name,
        interest_drivers=body.interest_drivers,
        apprehensions=body.apprehensions,
        notes=body.notes,
    )
    company_id = await db.interesting_companies.create(company)
    return {"id": company_id}


@router.patch("/{company_id}")
async def update_interesting_company(
    request: Request,
    company_id: str,
    body: UpdateInterestingCompanyRequest,
    candidate_id: str = Query(default="candidate_1"),
) -> dict[str, str]:
    db = request.app.state.db
    updates: dict[str, object] = {}
    if body.interest_drivers is not None:
        updates["interest_drivers"] = body.interest_drivers
    if body.apprehensions is not None:
        updates["apprehensions"] = body.apprehensions
    if body.notes is not None:
        updates["notes"] = body.notes

    if updates:
        await db.interesting_companies.update(candidate_id, company_id, **updates)
    return {"status": "updated"}


@router.delete("/{company_id}", status_code=204)
async def delete_interesting_company(
    request: Request,
    company_id: str,
    candidate_id: str = Query(default="candidate_1"),
) -> None:
    db = request.app.state.db
    await db.interesting_companies.delete(candidate_id, company_id)
