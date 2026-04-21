"""
Lightweight asyncpg adapter for persistent job tracking.
Matches the storage layer pattern (no SQLAlchemy).
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import asyncpg

log = logging.getLogger(__name__)


@dataclass
class _ItemTimer:
    login: str
    started_at: float = field(default_factory=time.monotonic)


class JobTracker:
    """Tracks a single ingest_job and its items against Postgres."""

    def __init__(self, pool: asyncpg.Pool, platform: str) -> None:
        self._pool = pool
        self._platform = platform
        self._job_id: str | None = None
        self._item_timers: dict[str, _ItemTimer] = {}

    @property
    def job_id(self) -> str | None:
        return self._job_id

    # ---- Job lifecycle ----

    async def create_job(
        self,
        job_type: str,
        trigger: str = "api",
        triggered_by: str | None = None,
        input_params: dict[str, Any] | None = None,
        concurrency: int | None = None,
    ) -> str:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO ingest_job (job_type, platform, trigger, triggered_by, input_params, concurrency)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                job_type,
                self._platform,
                trigger,
                triggered_by,
                json.dumps(input_params or {}),
                concurrency,
            )
        self._job_id = row["id"]
        return self._job_id

    async def mark_running(self) -> None:
        if not self._job_id:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE ingest_job
                SET status = 'running', started_at = now(), updated_at = now()
                WHERE id = $1
                """,
                self._job_id,
            )

    async def mark_completed(self, stats: dict[str, Any] | None = None) -> None:
        if not self._job_id:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE ingest_job
                SET status = 'completed',
                    completed_at = now(),
                    duration_ms = EXTRACT(EPOCH FROM (now() - started_at))::int * 1000,
                    total_items = $2,
                    succeeded_count = $3,
                    failed_count = $4,
                    skipped_count = $5,
                    stats = $6,
                    updated_at = now()
                WHERE id = $1
                """,
                self._job_id,
                (stats or {}).get("processed", 0),
                (stats or {}).get("succeeded", 0),
                (stats or {}).get("failed", 0),
                (stats or {}).get("skipped", 0),
                json.dumps(stats or {}),
            )

    async def mark_failed(self, error: str, error_detail: dict | None = None) -> None:
        if not self._job_id:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE ingest_job
                SET status = 'failed',
                    completed_at = now(),
                    duration_ms = CASE WHEN started_at IS NOT NULL
                        THEN EXTRACT(EPOCH FROM (now() - started_at))::int * 1000
                        ELSE NULL END,
                    error_summary = $2,
                    error_detail = $3,
                    updated_at = now()
                WHERE id = $1
                """,
                self._job_id,
                error[:1000],
                json.dumps(error_detail) if error_detail else None,
            )

    # ---- Item lifecycle ----

    async def item_started(self, login: str) -> None:
        if not self._job_id:
            return
        self._item_timers[login] = _ItemTimer(login=login)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO ingest_job_item (job_id, login, platform, status, started_at)
                VALUES ($1, $2, $3, 'running', now())
                """,
                self._job_id,
                login,
                self._platform,
            )

    async def item_completed(self, login: str, records_written: dict[str, int] | None = None) -> None:
        if not self._job_id:
            return
        duration_ms = self._pop_duration(login)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE ingest_job_item
                SET status = 'success',
                    completed_at = now(),
                    duration_ms = $3,
                    records_written = $4,
                    updated_at = now()
                WHERE job_id = $1 AND login = $2 AND status = 'running'
                """,
                self._job_id,
                login,
                duration_ms,
                json.dumps(records_written or {}),
            )

    async def item_failed(
        self, login: str, error_type: str, error_message: str
    ) -> None:
        if not self._job_id:
            return
        duration_ms = self._pop_duration(login)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE ingest_job_item
                SET status = 'failed',
                    completed_at = now(),
                    duration_ms = $3,
                    error_type = $4,
                    error_message = $5,
                    updated_at = now()
                WHERE job_id = $1 AND login = $2 AND status = 'running'
                """,
                self._job_id,
                login,
                duration_ms,
                error_type,
                error_message[:2000],
            )

    async def item_skipped(self, login: str) -> None:
        if not self._job_id:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO ingest_job_item (job_id, login, platform, status, completed_at)
                VALUES ($1, $2, $3, 'skipped', now())
                """,
                self._job_id,
                login,
                self._platform,
            )

    # ---- Queries ----

    @staticmethod
    async def get_job(pool: asyncpg.Pool, job_id: str) -> dict[str, Any] | None:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM ingest_job WHERE id = $1 AND is_deleted = FALSE", job_id
            )
        return dict(row) if row else None

    @staticmethod
    async def list_jobs(
        pool: asyncpg.Pool,
        limit: int = 20,
        offset: int = 0,
        platform: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions = ["is_deleted = FALSE"]
        params: list[Any] = []
        idx = 1
        if platform:
            conditions.append(f"platform = ${idx}")
            params.append(platform)
            idx += 1
        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1
        where = " AND ".join(conditions)
        params.extend([limit, offset])
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM ingest_job WHERE {where} "
                f"ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}",
                *params,
            )
        return [dict(r) for r in rows]

    @staticmethod
    async def get_job_items(
        pool: asyncpg.Pool,
        job_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM ingest_job_item WHERE job_id = $1 "
                "ORDER BY created_at LIMIT $2 OFFSET $3",
                job_id,
                limit,
                offset,
            )
        return [dict(r) for r in rows]

    # ---- Helpers ----

    def _pop_duration(self, login: str) -> int | None:
        timer = self._item_timers.pop(login, None)
        if timer:
            return int((time.monotonic() - timer.started_at) * 1000)
        return None
