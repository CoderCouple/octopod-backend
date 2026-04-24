"""Background scheduler that polls pipeline_schedule and spawns pipeline runs.

Follows the SendWorker pattern from app/outreach/send_worker.py.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import asyncpg
from croniter import croniter

from app.settings import settings

logger = logging.getLogger(__name__)


class PipelineScheduler:
    """Async worker that checks pipeline_schedule every 60s and fires due pipelines."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False
        self._pool: asyncpg.Pool | None = None

    async def start(self) -> None:
        self._running = True
        self._pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=3)
        self._task = asyncio.create_task(self._run())
        logger.info("PipelineScheduler started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._pool:
            await self._pool.close()
        logger.info("PipelineScheduler stopped")

    async def _run(self) -> None:
        poll_interval = 60

        while self._running:
            try:
                await self._poll_schedules()
            except Exception:
                logger.exception("PipelineScheduler: error polling schedules")

            await asyncio.sleep(poll_interval)

    async def _poll_schedules(self) -> None:
        assert self._pool is not None
        now = datetime.now(timezone.utc)

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, name, pipeline_type, input_params, cron_expression "
                "FROM pipeline_schedule "
                "WHERE is_enabled = TRUE AND next_run_at <= $1",
                now,
            )

        for row in rows:
            schedule_id = row["id"]
            pipeline_type = row["pipeline_type"]
            input_params = row["input_params"] or {}
            if isinstance(input_params, str):
                input_params = json.loads(input_params)

            logger.info(
                "Schedule %s (%s) is due — spawning %s pipeline",
                schedule_id, row["name"], pipeline_type,
            )

            # Spawn pipeline run as background task
            asyncio.create_task(
                self._run_pipeline(pipeline_type, input_params, schedule_id)
            )

            # Update last_run_at and compute next_run_at
            cron_expr = row["cron_expression"]
            cron = croniter(cron_expr, now)
            next_run = cron.get_next(datetime)

            async with self._pool.acquire() as conn:
                await conn.execute(
                    "UPDATE pipeline_schedule "
                    "SET last_run_at = $2, next_run_at = $3, updated_at = $4 "
                    "WHERE id = $1",
                    schedule_id, now, next_run, now,
                )

    async def _run_pipeline(
        self, pipeline_type: str, input_params: dict, schedule_id: str
    ) -> None:
        try:
            from app.ingest.pipeline.runner import PipelineRunner

            pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=2, max_size=5)
            try:
                runner = PipelineRunner(pool)
                await runner.run(
                    pipeline_type=pipeline_type,
                    trigger="schedule",
                    triggered_by=schedule_id,
                    input_params=input_params,
                )
            finally:
                await pool.close()
        except Exception:
            logger.exception(
                "Scheduled pipeline %s (schedule=%s) failed", pipeline_type, schedule_id
            )


# Module-level singleton
pipeline_scheduler = PipelineScheduler()
