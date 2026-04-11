"""Scheduler — orchestrates pipeline stages on cron schedules with master on/off switch."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from terrain.models.pipeline import PipelineRun, PipelineStageEnum, RunStatus, TriggerType
from terrain.pipeline.base import PipelineStage
from terrain.providers.db.base import CandidateRepository, PipelineRunRepository

logger = logging.getLogger(__name__)


class PipelineScheduler:
    """Manages scheduled and manual execution of pipeline stages.

    The scheduler has a master enabled/disabled toggle:
    - Enabled: scheduled and manual runs execute normally.
    - Disabled: runs are logged with status "skipped" instead of executing.
    """

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        run_repo: PipelineRunRepository,
        stages: dict[str, PipelineStage],
    ) -> None:
        self._cand_repo = candidate_repo
        self._run_repo = run_repo
        self._stages = stages
        self._scheduler = AsyncIOScheduler()
        self._running = False
        self._enabled = True
        self._active_tasks: dict[str, asyncio.Task] = {}

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
        logger.info("Scheduler %s", "enabled" if value else "disabled")

    async def _execute_stage(
        self,
        candidate_id: str,
        stage_name: str,
        trigger: TriggerType,
        source: Optional[str] = None,
    ) -> str:
        """Create a pipeline run and execute (or skip) the stage. Returns run_id."""
        stage_enum_name = stage_name.split("_")[0] if "_" in stage_name else stage_name
        try:
            stage_enum = PipelineStageEnum(stage_enum_name)
        except ValueError:
            stage_enum = PipelineStageEnum(stage_name)

        # If disabled, log as skipped
        if not self._enabled:
            run = PipelineRun(
                candidate_id=candidate_id,
                stage=stage_enum,
                source=source,
                trigger=trigger,
                status=RunStatus.SKIPPED,
                completed_at=datetime.now(timezone.utc),
            )
            run_id = await self._run_repo.create(run)
            logger.info("Stage %s skipped (scheduler disabled)", stage_name)
            return run_id

        run = PipelineRun(
            candidate_id=candidate_id,
            stage=stage_enum,
            source=source,
            trigger=trigger,
            status=RunStatus.RUNNING,
        )
        run_id = await self._run_repo.create(run)

        stage = self._stages.get(stage_name)
        if stage is None:
            logger.error("Stage %s not found in registered stages", stage_name)
            await self._run_repo.update(
                run_id,
                status=RunStatus.FAILED,
                completed_at=datetime.now(timezone.utc),
                error_log=[f"Stage {stage_name} not registered"],
            )
            return run_id

        try:
            result = await stage.run(candidate_id)
            await self._run_repo.update(
                run_id,
                status=RunStatus.COMPLETED,
                completed_at=datetime.now(timezone.utc),
                items_processed=result.items_processed,
                items_new=result.items_new,
                items_error=result.items_error,
                error_log=result.errors,
            )
            logger.info(
                "Stage %s completed: %d processed, %d new, %d errors",
                stage_name,
                result.items_processed,
                result.items_new,
                result.items_error,
            )
        except Exception as e:
            logger.exception("Stage %s failed", stage_name)
            await self._run_repo.update(
                run_id,
                status=RunStatus.FAILED,
                completed_at=datetime.now(timezone.utc),
                error_log=[str(e)],
            )

        # Clean up task reference
        self._active_tasks.pop(run_id, None)
        return run_id

    async def _scheduled_execute(
        self, candidate_id: str, stage_name: str, source: Optional[str] = None
    ) -> None:
        """Entry point for APScheduler cron jobs — wraps _execute_stage."""
        await self._execute_stage(candidate_id, stage_name, TriggerType.SCHEDULED, source)

    async def trigger_manual(
        self, candidate_id: str, stage_name: str
    ) -> str:
        """Trigger a manual run as a background task. Returns run_id immediately."""
        if not self._enabled:
            # Still create the run record, but mark as skipped
            return await self._execute_stage(
                candidate_id, stage_name, TriggerType.MANUAL
            )

        stage_enum_name = stage_name.split("_")[0] if "_" in stage_name else stage_name
        try:
            stage_enum = PipelineStageEnum(stage_enum_name)
        except ValueError:
            stage_enum = PipelineStageEnum(stage_name)

        # Create the run record immediately
        run = PipelineRun(
            candidate_id=candidate_id,
            stage=stage_enum,
            trigger=TriggerType.MANUAL,
            status=RunStatus.RUNNING,
        )
        run_id = await self._run_repo.create(run)

        stage = self._stages.get(stage_name)
        if stage is None:
            await self._run_repo.update(
                run_id,
                status=RunStatus.FAILED,
                completed_at=datetime.now(timezone.utc),
                error_log=[f"Stage {stage_name} not registered"],
            )
            return run_id

        # Launch as background task
        async def _run_background() -> None:
            try:
                result = await stage.run(candidate_id)
                await self._run_repo.update(
                    run_id,
                    status=RunStatus.COMPLETED,
                    completed_at=datetime.now(timezone.utc),
                    items_processed=result.items_processed,
                    items_new=result.items_new,
                    items_error=result.items_error,
                    error_log=result.errors,
                )
                logger.info(
                    "Manual %s completed: %d processed, %d new",
                    stage_name,
                    result.items_processed,
                    result.items_new,
                )
            except Exception as e:
                logger.exception("Manual %s failed", stage_name)
                await self._run_repo.update(
                    run_id,
                    status=RunStatus.FAILED,
                    completed_at=datetime.now(timezone.utc),
                    error_log=[str(e)],
                )
            finally:
                self._active_tasks.pop(run_id, None)

        task = asyncio.create_task(_run_background())
        self._active_tasks[run_id] = task
        return run_id

    async def load_schedules(self, candidate_id: str) -> int:
        """Load cron schedules from candidate config. Returns number of jobs added."""
        candidate = await self._cand_repo.get(candidate_id)
        if candidate is None:
            logger.error("Candidate %s not found", candidate_id)
            return 0

        schedules = candidate.schedules
        jobs_added = 0

        schedule_map = {
            "harvest_linkedin": ("harvest", "linkedin"),
            "harvest_jobright": ("harvest", "jobright"),
            "score_batch": ("scoring", None),
            "cover_letter_batch": ("cover_letter", None),
        }

        for field_name, (stage_name, source) in schedule_map.items():
            cron_expr = getattr(schedules, field_name, None)
            if not cron_expr:
                continue

            parts = cron_expr.split()
            if len(parts) != 5:
                logger.warning("Invalid cron expression for %s: %s", field_name, cron_expr)
                continue

            trigger = CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
            )

            job_id = f"{candidate_id}_{field_name}"
            self._scheduler.add_job(
                self._scheduled_execute,
                trigger=trigger,
                id=job_id,
                args=[candidate_id, stage_name, source],
                replace_existing=True,
            )
            jobs_added += 1
            logger.info("Scheduled %s: %s", job_id, cron_expr)

        return jobs_added

    def start(self) -> None:
        """Start the APScheduler event loop."""
        if not self._running:
            self._scheduler.start()
            self._running = True
            logger.info("Scheduler started")

    def stop(self) -> None:
        """Stop the APScheduler event loop."""
        if self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Scheduler stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def get_jobs(self) -> list[dict[str, str]]:
        """Return list of scheduled cron jobs with their next run times."""
        jobs = []
        for job in self._scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "next_run": str(job.next_run_time) if job.next_run_time else "paused",
            })
        return jobs

    def get_active_runs(self) -> list[str]:
        """Return run IDs of currently executing background tasks."""
        return [rid for rid, task in self._active_tasks.items() if not task.done()]
