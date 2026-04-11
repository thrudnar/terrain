"""Pipeline API routes — trigger stages, view runs, scheduler control, costs."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from terrain.models.pipeline import PipelineRun, StageResult

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


class RunRequest(BaseModel):
    candidate_id: str = "candidate_1"
    options: Optional[dict[str, object]] = None


class RunOneRequest(BaseModel):
    candidate_id: str = "candidate_1"
    opportunity_id: str


class RunTriggeredResponse(BaseModel):
    run_id: str
    stage: str
    status: str


class PipelineRunListResponse(BaseModel):
    items: list[PipelineRun]
    count: int


class SchedulerStatusResponse(BaseModel):
    running: bool
    enabled: bool
    jobs: list[dict[str, str]]
    active_runs: list[str]


class SchedulerToggleRequest(BaseModel):
    enabled: bool


class CostSummaryResponse(BaseModel):
    costs_by_task: dict[str, float]
    since: datetime


@router.post("/{stage}/run", response_model=RunTriggeredResponse)
async def run_stage(
    request: Request,
    stage: str,
    body: RunRequest,
) -> RunTriggeredResponse:
    """Trigger a manual pipeline stage run. Returns immediately with run_id.
    The stage executes in the background. Poll /api/pipeline/runs to check status.
    """
    scheduler = request.app.state.scheduler
    stages = request.app.state.stages
    if stage not in stages:
        raise HTTPException(status_code=404, detail=f"Stage '{stage}' not found")

    run_id = await scheduler.trigger_manual(body.candidate_id, stage)

    # Determine initial status
    status = "skipped" if not scheduler.enabled else "running"

    return RunTriggeredResponse(run_id=run_id, stage=stage, status=status)


@router.post("/{stage}/run-one", response_model=StageResult)
async def run_stage_one(
    request: Request,
    stage: str,
    body: RunOneRequest,
) -> StageResult:
    """Run a pipeline stage for a single opportunity. Runs synchronously (fast)."""
    stages = request.app.state.stages
    if stage not in stages:
        raise HTTPException(status_code=404, detail=f"Stage '{stage}' not found")
    result = await stages[stage].run_one(body.candidate_id, body.opportunity_id)
    return result


@router.get("/runs", response_model=PipelineRunListResponse)
async def list_runs(
    request: Request,
    candidate_id: str = Query(default="candidate_1"),
    limit: int = Query(default=50, le=200),
) -> PipelineRunListResponse:
    db = request.app.state.db
    runs = await db.pipeline_runs.find_by_candidate(candidate_id, limit)
    return PipelineRunListResponse(items=runs, count=len(runs))


@router.get("/runs/{run_id}", response_model=PipelineRun)
async def get_run(
    request: Request,
    run_id: str,
) -> PipelineRun:
    """Get a single pipeline run by ID. Useful for polling background run status."""
    db = request.app.state.db
    # Find across all candidates — run_id is globally unique
    from bson import ObjectId
    doc = await db._db["pipeline_runs"].find_one({"_id": ObjectId(run_id)})
    if doc is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    doc["_id"] = str(doc["_id"])
    return PipelineRun.model_validate(doc)


@router.get("/status", response_model=SchedulerStatusResponse)
async def scheduler_status(request: Request) -> SchedulerStatusResponse:
    scheduler = request.app.state.scheduler
    return SchedulerStatusResponse(
        running=scheduler.is_running,
        enabled=scheduler.enabled,
        jobs=scheduler.get_jobs(),
        active_runs=scheduler.get_active_runs(),
    )


@router.post("/scheduler/toggle", response_model=SchedulerStatusResponse)
async def toggle_scheduler(
    request: Request,
    body: SchedulerToggleRequest,
) -> SchedulerStatusResponse:
    """Enable or disable the scheduler. When disabled, all runs (scheduled and manual) are skipped."""
    scheduler = request.app.state.scheduler
    scheduler.enabled = body.enabled
    return SchedulerStatusResponse(
        running=scheduler.is_running,
        enabled=scheduler.enabled,
        jobs=scheduler.get_jobs(),
        active_runs=scheduler.get_active_runs(),
    )


@router.get("/costs", response_model=CostSummaryResponse)
async def cost_summary(
    request: Request,
    candidate_id: str = Query(default="candidate_1"),
    days: int = Query(default=30, le=365),
) -> CostSummaryResponse:
    from datetime import timedelta

    db = request.app.state.db
    since = datetime.now(timezone.utc) - timedelta(days=days)
    costs = await db.api_usage.get_cost_summary(candidate_id, since)
    return CostSummaryResponse(costs_by_task=costs, since=since)
