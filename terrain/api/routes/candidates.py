"""Candidate API routes."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from terrain.models.candidate import ActivePrompts, AIRoutingConfig, Candidate

router = APIRouter(prefix="/api/candidates", tags=["candidates"])


class PromptsUpdate(BaseModel):
    scoring: str | None = None
    cover_letter: str | None = None
    dedup: str | None = None


@router.get("/{candidate_id}", response_model=Candidate)
async def get_candidate(request: Request, candidate_id: str) -> Candidate:
    db = request.app.state.db
    candidate = await db.candidates.get(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


@router.patch("/{candidate_id}/prompts")
async def update_prompts(
    request: Request,
    candidate_id: str,
    body: PromptsUpdate,
) -> dict[str, str]:
    db = request.app.state.db
    candidate = await db.candidates.get(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    current = candidate.active_prompts
    updated = ActivePrompts(
        scoring=body.scoring or current.scoring,
        cover_letter=body.cover_letter or current.cover_letter,
        dedup=body.dedup or current.dedup,
    )
    await db.candidates.update_active_prompts(candidate_id, updated)
    return {"status": "updated"}


@router.get("/{candidate_id}/routing", response_model=AIRoutingConfig | None)
async def get_routing(request: Request, candidate_id: str) -> AIRoutingConfig | None:
    db = request.app.state.db
    return await db.candidates.get_ai_routing(candidate_id)
