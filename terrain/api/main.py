"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from terrain.config.settings import get_settings

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: str
    environment: str
    database: str
    ollama: str
    scheduler: str
    uptime_seconds: float


_start_time: datetime | None = None


def _build_pipeline_stages(db: "MongoDatabaseClient", anthropic: "AnthropicProvider", ollama: "OllamaProvider") -> dict:
    """Construct all pipeline stages with their real dependencies."""
    from terrain.pipeline.cover_letter import CoverLetterGenerator
    from terrain.pipeline.dedup import Dedup
    from terrain.pipeline.harvest.base import SourceConfig
    from terrain.pipeline.harvest.linkedin import LinkedInHarvester
    from terrain.pipeline.harvest.stage import HarvestStage
    from terrain.pipeline.promoter import Promoter
    from terrain.pipeline.scorer import Scorer

    settings = get_settings()

    # Harvest stage — LinkedIn with persistent browser profile
    linkedin = LinkedInHarvester(profile_dir=settings.linkedin_profile_dir)
    harvest_config = SourceConfig(
        board="linkedin",
        collections=["top-applicant", "recommended", "remote-jobs"],
    )

    stages: dict[str, object] = {
        "harvest": HarvestStage(linkedin, db.opportunities, db.candidates, harvest_config),
        "dedup": Dedup(db.opportunities, db.candidates, ollama, settings.prompts_dir),
        "promotion": Promoter(db.opportunities, db.interesting_companies),
    }

    # Scoring and cover letter require Anthropic API key
    if anthropic:
        stages["scoring"] = Scorer(db.opportunities, db.candidates, anthropic, settings.prompts_dir)
        stages["cover_letter"] = CoverLetterGenerator(db.opportunities, db.candidates, anthropic, settings.prompts_dir)

    return stages


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — initialize services on startup, clean up on shutdown."""
    global _start_time
    from terrain.pipeline.scheduler import PipelineScheduler
    from terrain.providers.ai.anthropic import AnthropicProvider
    from terrain.providers.ai.ollama import OllamaProvider
    from terrain.providers.db.mongo import MongoDatabaseClient

    settings = get_settings()
    _start_time = datetime.now(timezone.utc)

    # Initialize database
    db = MongoDatabaseClient(settings.mongo_uri)
    try:
        await db.initialize()
        logger.info("MongoDB connected and indexes created")
    except Exception as e:
        logger.warning("MongoDB initialization failed: %s", e)

    # Initialize AI providers
    usage_logger = db.api_usage.log if settings.anthropic_api_key else None
    anthropic = AnthropicProvider(
        api_key=settings.anthropic_api_key,
        usage_logger=usage_logger,
    ) if settings.anthropic_api_key else None

    ollama = OllamaProvider(base_url=settings.ollama_url)

    # Build pipeline stages (harvest + dedup work without Anthropic)
    stages = _build_pipeline_stages(db, anthropic, ollama)

    # Initialize scheduler
    scheduler = PipelineScheduler(db.candidates, db.pipeline_runs, stages)
    if stages:
        try:
            jobs = await scheduler.load_schedules("candidate_1")
            if jobs > 0:
                scheduler.start()
                logger.info("Scheduler started with %d jobs", jobs)
        except Exception as e:
            logger.warning("Scheduler initialization failed: %s", e)

    # Store on app state for route access
    app.state.db = db
    app.state.anthropic = anthropic
    app.state.ollama = ollama
    app.state.scheduler = scheduler
    app.state.stages = stages

    yield

    # Shutdown
    scheduler.stop()
    if ollama:
        await ollama.close()
    db.close()
    logger.info("Application shut down")


app = FastAPI(
    title="terrAIn",
    description="Job hunting pipeline API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
from terrain.api.routes import candidates, interesting_companies, opportunities, pipeline  # noqa: E402

app.include_router(opportunities.router)
app.include_router(pipeline.router)
app.include_router(candidates.router)
app.include_router(interesting_companies.router)


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint — verifies service connectivity."""
    from fastapi import Request

    settings = get_settings()
    now = datetime.now(timezone.utc)
    uptime = (now - _start_time).total_seconds() if _start_time else 0.0

    # Check real connectivity
    db_status = "not_connected"
    ollama_status = "not_connected"
    scheduler_status = "stopped"

    try:
        if hasattr(app.state, "db"):
            await app.state.db._db.command("ping")
            db_status = "connected"
    except Exception:
        db_status = "error"

    try:
        if hasattr(app.state, "ollama") and app.state.ollama:
            if await app.state.ollama.check_health():
                ollama_status = "connected"
    except Exception:
        ollama_status = "error"

    if hasattr(app.state, "scheduler") and app.state.scheduler.is_running:
        scheduler_status = "running"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        environment=settings.environment,
        database=db_status,
        ollama=ollama_status,
        scheduler=scheduler_status,
        uptime_seconds=uptime,
    )
