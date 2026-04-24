"""
Pipeline execution tracker — persists pipeline_execution + pipeline_execution_step
rows in Postgres via raw asyncpg. Mirrors the JobTracker pattern.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import asyncpg

from app.common.enum.ingest import ControlSignal, PipelineStatus, StepStatus

log = logging.getLogger(__name__)


class PipelineTracker:
    """Tracks a single pipeline execution and its steps against Postgres."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        self._execution_id: str | None = None
        self._started_at_mono: float | None = None

    @property
    def execution_id(self) -> str | None:
        return self._execution_id

    # ---- Execution lifecycle ----

    async def create_execution(
        self,
        pipeline_type: str,
        steps: list[dict[str, str]],
        trigger: str = "cli",
        triggered_by: str | None = None,
        input_params: dict[str, Any] | None = None,
    ) -> str:
        exec_id = f"pe_{uuid.uuid4().hex[:12]}"
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO pipeline_execution
                    (id, pipeline_type, status, control_signal, trigger, triggered_by,
                     input_params, total_steps)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                exec_id,
                pipeline_type,
                PipelineStatus.PENDING,
                ControlSignal.NONE,
                trigger,
                triggered_by,
                json.dumps(input_params or {}),
                len(steps),
            )
            for i, step in enumerate(steps, start=1):
                await conn.execute(
                    """
                    INSERT INTO pipeline_execution_step
                        (id, pipeline_execution_id, step_order, step_name, step_label, status)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    f"pes_{uuid.uuid4().hex[:12]}",
                    exec_id,
                    i,
                    step["name"],
                    step["label"],
                    StepStatus.PENDING,
                )
        self._execution_id = exec_id
        return exec_id

    async def mark_execution_running(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE pipeline_execution
                SET status = $2, started_at = now(), updated_at = now()
                WHERE id = $1
                """,
                self._execution_id,
                PipelineStatus.RUNNING,
            )

    async def mark_execution_completed(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE pipeline_execution
                SET status = $2,
                    completed_at = now(),
                    duration_ms = EXTRACT(EPOCH FROM (now() - started_at))::int * 1000,
                    updated_at = now()
                WHERE id = $1
                """,
                self._execution_id,
                PipelineStatus.COMPLETED,
            )

    async def mark_execution_failed(self, error: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE pipeline_execution
                SET status = $2,
                    completed_at = now(),
                    duration_ms = CASE WHEN started_at IS NOT NULL
                        THEN EXTRACT(EPOCH FROM (now() - started_at))::int * 1000
                        ELSE NULL END,
                    error_summary = $3,
                    updated_at = now()
                WHERE id = $1
                """,
                self._execution_id,
                PipelineStatus.FAILED,
                error[:1000],
            )

    async def mark_execution_paused(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE pipeline_execution
                SET status = $2, updated_at = now()
                WHERE id = $1
                """,
                self._execution_id,
                PipelineStatus.PAUSED,
            )

    async def mark_execution_cancelled(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE pipeline_execution
                SET status = $2,
                    completed_at = now(),
                    duration_ms = CASE WHEN started_at IS NOT NULL
                        THEN EXTRACT(EPOCH FROM (now() - started_at))::int * 1000
                        ELSE NULL END,
                    updated_at = now()
                WHERE id = $1
                """,
                self._execution_id,
                PipelineStatus.CANCELLED,
            )

    # ---- Step lifecycle ----

    async def mark_step_running(self, step_order: int, ingest_job_id: str | None = None) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE pipeline_execution_step
                SET status = $3, started_at = now(), ingest_job_id = $4, updated_at = now()
                WHERE pipeline_execution_id = $1 AND step_order = $2
                """,
                self._execution_id,
                step_order,
                StepStatus.RUNNING,
                ingest_job_id,
            )
            await conn.execute(
                """
                UPDATE pipeline_execution
                SET current_step_order = $2, updated_at = now()
                WHERE id = $1
                """,
                self._execution_id,
                step_order,
            )

    async def mark_step_completed(self, step_order: int, stats: dict[str, Any] | None = None) -> None:
        s = stats or {}
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE pipeline_execution_step
                SET status = $3,
                    completed_at = now(),
                    duration_ms = EXTRACT(EPOCH FROM (now() - started_at))::int * 1000,
                    total_items = $4,
                    succeeded_count = $5,
                    failed_count = $6,
                    skipped_count = $7,
                    stats = $8,
                    updated_at = now()
                WHERE pipeline_execution_id = $1 AND step_order = $2
                """,
                self._execution_id,
                step_order,
                StepStatus.COMPLETED,
                s.get("total", s.get("processed", 0)),
                s.get("succeeded", 0),
                s.get("failed", 0),
                s.get("skipped", 0),
                json.dumps(s),
            )
            await conn.execute(
                """
                UPDATE pipeline_execution
                SET completed_steps = completed_steps + 1, updated_at = now()
                WHERE id = $1
                """,
                self._execution_id,
            )

    async def mark_step_failed(self, step_order: int, error: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE pipeline_execution_step
                SET status = $3,
                    completed_at = now(),
                    duration_ms = CASE WHEN started_at IS NOT NULL
                        THEN EXTRACT(EPOCH FROM (now() - started_at))::int * 1000
                        ELSE NULL END,
                    error_summary = $4,
                    updated_at = now()
                WHERE pipeline_execution_id = $1 AND step_order = $2
                """,
                self._execution_id,
                step_order,
                StepStatus.FAILED,
                error[:1000],
            )

    async def mark_step_skipped(self, step_order: int) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE pipeline_execution_step
                SET status = $3, completed_at = now(), updated_at = now()
                WHERE pipeline_execution_id = $1 AND step_order = $2
                """,
                self._execution_id,
                step_order,
                StepStatus.SKIPPED,
            )

    async def mark_step_cancelled(self, step_order: int) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE pipeline_execution_step
                SET status = $3, completed_at = now(), updated_at = now()
                WHERE pipeline_execution_id = $1 AND step_order = $2
                """,
                self._execution_id,
                step_order,
                StepStatus.CANCELLED,
            )

    async def update_step_progress(
        self, step_order: int, total: int, succeeded: int, failed: int, skipped: int = 0
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE pipeline_execution_step
                SET total_items = $3, succeeded_count = $4, failed_count = $5,
                    skipped_count = $6, updated_at = now()
                WHERE pipeline_execution_id = $1 AND step_order = $2
                """,
                self._execution_id,
                step_order,
                total,
                succeeded,
                failed,
                skipped,
            )

    # ---- Control signal ----

    async def check_control_signal(self) -> str:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT control_signal FROM pipeline_execution WHERE id = $1",
                self._execution_id,
            )
        return row["control_signal"] if row else ControlSignal.NONE

    async def clear_control_signal(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE pipeline_execution
                SET control_signal = $2, updated_at = now()
                WHERE id = $1
                """,
                self._execution_id,
                ControlSignal.NONE,
            )

    # ---- Static queries ----

    @staticmethod
    async def set_control_signal(pool: asyncpg.Pool, execution_id: str, signal: str) -> bool:
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE pipeline_execution
                SET control_signal = $2, updated_at = now()
                WHERE id = $1 AND status IN ('running', 'paused')
                """,
                execution_id,
                signal,
            )
        return result != "UPDATE 0"

    @staticmethod
    async def get_execution(pool: asyncpg.Pool, execution_id: str) -> dict[str, Any] | None:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, pipeline_type, status, control_signal, trigger, triggered_by,
                       input_params, total_steps, completed_steps, current_step_order,
                       started_at, completed_at, duration_ms, error_summary,
                       created_at, updated_at
                FROM pipeline_execution WHERE id = $1
                """,
                execution_id,
            )
            if not row:
                return None
            steps = await conn.fetch(
                """
                SELECT id, step_order, step_name, step_label, status, ingest_job_id,
                       total_items, succeeded_count, failed_count, skipped_count,
                       started_at, completed_at, duration_ms, error_summary, stats
                FROM pipeline_execution_step
                WHERE pipeline_execution_id = $1
                ORDER BY step_order
                """,
                execution_id,
            )
        result = dict(row)
        result["steps"] = [dict(s) for s in steps]
        return result

    @staticmethod
    async def get_active_executions(pool: asyncpg.Pool) -> list[dict[str, Any]]:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, pipeline_type, status, control_signal, total_steps,
                       completed_steps, current_step_order, started_at, input_params
                FROM pipeline_execution
                WHERE status IN ('running', 'paused')
                ORDER BY started_at DESC
                """,
            )
        return [dict(r) for r in rows]

    @staticmethod
    async def resume_execution(pool: asyncpg.Pool, execution_id: str) -> bool:
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE pipeline_execution
                SET status = $2, control_signal = $3, updated_at = now()
                WHERE id = $1 AND status = 'paused'
                """,
                execution_id,
                PipelineStatus.RUNNING,
                ControlSignal.NONE,
            )
        return result != "UPDATE 0"

    @staticmethod
    async def get_next_pending_step(pool: asyncpg.Pool, execution_id: str) -> int | None:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT step_order FROM pipeline_execution_step
                WHERE pipeline_execution_id = $1 AND status = 'pending'
                ORDER BY step_order LIMIT 1
                """,
                execution_id,
            )
        return row["step_order"] if row else None

    @staticmethod
    async def mark_stale_running_as_paused(pool: asyncpg.Pool) -> int:
        """On startup, mark any running executions as paused (safe to resume)."""
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE pipeline_execution
                SET status = 'paused', control_signal = 'none', updated_at = now()
                WHERE status = 'running'
                """,
            )
        count = int(result.split()[-1]) if result else 0
        return count
