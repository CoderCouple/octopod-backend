"""API endpoints for job monitoring, status, and retry."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import Any

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.api.tags import Tags
from app.api.v1.request.ingest_request import RetryRequest
from app.api.v1.response.base_response import BaseResponse, error_response, success_response
from app.api.v1.response.ingest_response import (
    IngestStatusResponse,
    JobControlResponse,
    JobDetail,
    JobItem,
    JobSummary,
    RetryStartedResponse,
)
from app.common.auth.auth import get_actor_id_required
from app.common.enum.ingest import ControlSignal, IngestJobType, IngestTrigger
from app.common.ingest_common import (
    _fetch_gh_user_data,
    _fetch_hf_user_data,
    _serialize_row,
)
from app.settings import settings

router = APIRouter(prefix="/ingest", tags=[Tags.Ingestion])

log = logging.getLogger(__name__)


# ---- Status & Retry ----


@router.get("/status", response_model=BaseResponse[IngestStatusResponse])
async def ingest_status(_actor_id: str = Depends(get_actor_id_required)) -> BaseResponse:
    try:
        conn = await asyncpg.connect(settings.asyncpg_dsn)
        try:
            gh = await conn.fetch(
                "SELECT status, COUNT(*) as cnt FROM gh_checkpoints GROUP BY status"
            )
            hf = await conn.fetch(
                "SELECT status, COUNT(*) as cnt FROM hf_checkpoints GROUP BY status"
            )
            recent_jobs = await conn.fetch(
                "SELECT id, job_type, platform, status, started_at, completed_at, "
                "total_items, succeeded_count, failed_count, skipped_count "
                "FROM ingest_job WHERE is_deleted = FALSE "
                "ORDER BY created_at DESC LIMIT 10"
            )
        finally:
            await conn.close()
        return success_response({
            "github": {r["status"]: r["cnt"] for r in gh},
            "huggingface": {r["status"]: r["cnt"] for r in hf},
            "recent_jobs": [_serialize_row(dict(r)) for r in recent_jobs],
        })
    except Exception as e:
        return error_response(str(e), 500)


@router.post("/retry", response_model=BaseResponse[RetryStartedResponse])
async def retry_failed(
    req: RetryRequest, background_tasks: BackgroundTasks,
    _actor_id: str = Depends(get_actor_id_required),
) -> BaseResponse:
    # Create job records for both platforms
    pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
    try:
        from app.ingest.common.job_tracker import JobTracker

        gh_tracker = JobTracker(pool, "github")
        gh_job_id = await gh_tracker.create_job(
            job_type=IngestJobType.GH_RETRY,
            trigger=IngestTrigger.API,
            input_params={"status": req.status, "max_attempts": req.max_attempts},
        )
        hf_tracker = JobTracker(pool, "huggingface")
        hf_job_id = await hf_tracker.create_job(
            job_type=IngestJobType.HF_RETRY,
            trigger=IngestTrigger.API,
            input_params={"status": req.status, "max_attempts": req.max_attempts},
        )
    finally:
        await pool.close()

    async def _run() -> None:
        try:
            from app.ingest.common.job_tracker import JobTracker

            conn = await asyncpg.connect(settings.asyncpg_dsn)
            try:
                gh_rows = await conn.fetch(
                    "SELECT login FROM gh_checkpoints WHERE status = $1 AND attempt_count < $2",
                    req.status,
                    req.max_attempts,
                )
                hf_rows = await conn.fetch(
                    "SELECT username FROM hf_checkpoints WHERE status = $1 AND attempt_count < $2",
                    req.status,
                    req.max_attempts,
                )
            finally:
                await conn.close()

            if gh_rows:
                from app.ingest.gh.client import GitHubClient
                from app.ingest.gh.config import GHConfig
                from app.ingest.gh.orchestrator import GHOrchestrator
                from app.ingest.gh.storage import GHStorage
                from app.ingest.gh.token_pool import TokenPool

                config = GHConfig()
                config.validate()
                token_pool = TokenPool(config.github_tokens)
                storage = GHStorage(config.db_dsn, config.db_pool_min, config.db_pool_max)
                await storage.connect()
                try:
                    tracker = JobTracker(storage.pool, "github")
                    tracker._job_id = gh_job_id
                    await tracker.mark_running()
                    async with GitHubClient(config, token_pool) as client:
                        orch = GHOrchestrator(config, client, storage, job_tracker=tracker)
                        stats = await orch.run([r["login"] for r in gh_rows])
                        await tracker.mark_completed(asdict(stats))
                finally:
                    await storage.close()
            else:
                p = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
                try:
                    t = JobTracker(p, "github")
                    t._job_id = gh_job_id
                    await t.mark_completed({"processed": 0, "succeeded": 0, "failed": 0, "skipped": 0})
                finally:
                    await p.close()

            if hf_rows:
                from app.ingest.hf.client import HFClient
                from app.ingest.hf.config import HFConfig
                from app.ingest.hf.orchestrator import HFOrchestrator
                from app.ingest.hf.storage import HFStorage

                hf_config = HFConfig()
                hf_config.validate()
                hf_storage = HFStorage(hf_config.db_dsn, hf_config.db_pool_min, hf_config.db_pool_max)
                await hf_storage.connect()
                try:
                    tracker = JobTracker(hf_storage.pool, "huggingface")
                    tracker._job_id = hf_job_id
                    await tracker.mark_running()
                    async with HFClient(hf_config) as hf_client:
                        orch = HFOrchestrator(hf_config, hf_client, hf_storage, job_tracker=tracker)
                        stats = await orch.run([r["username"] for r in hf_rows])
                        await tracker.mark_completed(asdict(stats))
                finally:
                    await hf_storage.close()
            else:
                p = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
                try:
                    t = JobTracker(p, "huggingface")
                    t._job_id = hf_job_id
                    await t.mark_completed({"processed": 0, "succeeded": 0, "failed": 0, "skipped": 0})
                finally:
                    await p.close()

        except Exception as e:
            log.exception("retry job failed")
            try:
                p = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
                try:
                    for jid, plat in [(gh_job_id, "github"), (hf_job_id, "huggingface")]:
                        t = JobTracker(p, plat)
                        t._job_id = jid
                        await t.mark_failed(str(e))
                finally:
                    await p.close()
            except Exception:
                pass

    background_tasks.add_task(lambda: asyncio.run(_run()))
    return success_response({
        "gh_job_id": gh_job_id,
        "hf_job_id": hf_job_id,
        "status": "started",
    })


# ---- Job listing & detail endpoints ----


@router.get("/jobs", response_model=BaseResponse[list[JobSummary]])
async def list_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    platform: str | None = Query(default=None),
    status: str | None = Query(default=None),
    _actor_id: str = Depends(get_actor_id_required),
) -> BaseResponse:
    try:

        conn = await asyncpg.connect(settings.asyncpg_dsn)
        try:
            # Build query with optional filters
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
            rows = await conn.fetch(
                f"SELECT id, job_type, platform, status, trigger, triggered_by, "
                f"execution_phase_id, input_params, concurrency, started_at, "
                f"completed_at, duration_ms, total_items, succeeded_count, "
                f"failed_count, skipped_count, error_summary, error_detail, "
                f"stats, is_deleted, created_at, updated_at "
                f"FROM ingest_job WHERE {where} "
                f"ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}",
                *params,
            )
        finally:
            await conn.close()
        return success_response([_serialize_row(dict(r)) for r in rows])
    except Exception as e:
        return error_response(str(e), 500)


@router.get("/jobs/{job_id}", response_model=BaseResponse[JobDetail])
async def get_job(job_id: str, _actor_id: str = Depends(get_actor_id_required)) -> BaseResponse:
    try:
        conn = await asyncpg.connect(settings.asyncpg_dsn)
        try:
            row = await conn.fetchrow(
                "SELECT id, job_type, platform, status, trigger, triggered_by, "
                "execution_phase_id, input_params, concurrency, started_at, "
                "completed_at, duration_ms, total_items, succeeded_count, "
                "failed_count, skipped_count, error_summary, error_detail, "
                "stats, is_deleted, created_at, updated_at "
                "FROM ingest_job WHERE id = $1 AND is_deleted = FALSE",
                job_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="Job not found")

            # Item counts summary
            item_counts = await conn.fetch(
                "SELECT status, COUNT(*) as cnt FROM ingest_job_item "
                "WHERE job_id = $1 GROUP BY status",
                job_id,
            )
        finally:
            await conn.close()

        result = _serialize_row(dict(row))
        result["item_counts"] = {r["status"]: r["cnt"] for r in item_counts}
        return success_response(result)
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), 500)


@router.get("/jobs/{job_id}/items", response_model=BaseResponse[list[JobItem]])
async def get_job_items(
    job_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _actor_id: str = Depends(get_actor_id_required),
) -> BaseResponse:
    try:
        conn = await asyncpg.connect(settings.asyncpg_dsn)
        try:
            # Verify job exists
            job = await conn.fetchrow(
                "SELECT id FROM ingest_job WHERE id = $1 AND is_deleted = FALSE", job_id
            )
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")

            rows = await conn.fetch(
                "SELECT id, job_id, login, platform, status, attempt_number, "
                "started_at, completed_at, duration_ms, records_written, "
                "error_type, error_message, created_at, updated_at "
                "FROM ingest_job_item WHERE job_id = $1 "
                "ORDER BY created_at LIMIT $2 OFFSET $3",
                job_id,
                limit,
                offset,
            )
        finally:
            await conn.close()
        return success_response([_serialize_row(dict(r)) for r in rows])
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), 500)


# ---- Job control endpoints (pause / resume / cancel) ----


@router.post("/jobs/{job_id}/pause", response_model=BaseResponse[JobControlResponse])
async def pause_job(job_id: str, _actor_id: str = Depends(get_actor_id_required)) -> BaseResponse:
    from app.ingest.common.job_tracker import JobTracker

    try:
        conn = await asyncpg.connect(settings.asyncpg_dsn)
        try:
            row = await conn.fetchrow(
                "SELECT id, status FROM ingest_job WHERE id = $1 AND is_deleted = FALSE",
                job_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="Job not found")
            if row["status"] not in ("running",):
                raise HTTPException(
                    status_code=409, detail=f"Cannot pause job with status '{row['status']}'"
                )
        finally:
            await conn.close()

        pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
        try:
            ok = await JobTracker.set_control_signal(pool, job_id, ControlSignal.PAUSE)
        finally:
            await pool.close()

        if not ok:
            raise HTTPException(status_code=409, detail="Failed to set pause signal")
        return success_response({"job_id": job_id, "control_signal": "pause"})
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), 500)


@router.post("/jobs/{job_id}/resume", response_model=BaseResponse[JobControlResponse])
async def resume_job(job_id: str, _actor_id: str = Depends(get_actor_id_required)) -> BaseResponse:
    from app.ingest.common.job_tracker import JobTracker

    try:
        conn = await asyncpg.connect(settings.asyncpg_dsn)
        try:
            row = await conn.fetchrow(
                "SELECT id, status FROM ingest_job WHERE id = $1 AND is_deleted = FALSE",
                job_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="Job not found")
            if row["status"] != "paused":
                raise HTTPException(
                    status_code=409, detail=f"Cannot resume job with status '{row['status']}'"
                )
        finally:
            await conn.close()

        pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
        try:
            ok = await JobTracker.resume_job(pool, job_id)
        finally:
            await pool.close()

        if not ok:
            raise HTTPException(status_code=409, detail="Failed to resume job")
        return success_response({"job_id": job_id, "control_signal": "none"})
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), 500)


@router.post("/jobs/{job_id}/cancel", response_model=BaseResponse[JobControlResponse])
async def cancel_job(job_id: str, _actor_id: str = Depends(get_actor_id_required)) -> BaseResponse:
    from app.ingest.common.job_tracker import JobTracker

    try:
        conn = await asyncpg.connect(settings.asyncpg_dsn)
        try:
            row = await conn.fetchrow(
                "SELECT id, status FROM ingest_job WHERE id = $1 AND is_deleted = FALSE",
                job_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="Job not found")
            if row["status"] not in ("running", "paused"):
                raise HTTPException(
                    status_code=409, detail=f"Cannot cancel job with status '{row['status']}'"
                )
        finally:
            await conn.close()

        pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
        try:
            ok = await JobTracker.set_control_signal(pool, job_id, ControlSignal.CANCEL)
        finally:
            await pool.close()

        if not ok:
            raise HTTPException(status_code=409, detail="Failed to set cancel signal")
        return success_response({"job_id": job_id, "control_signal": "cancel"})
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), 500)


# ---- Job data endpoints (actual ingested data) ----


@router.get("/jobs/{job_id}/data", response_model=BaseResponse[list[dict[str, Any]]])
async def get_job_data(
    job_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _actor_id: str = Depends(get_actor_id_required),
) -> BaseResponse:
    """Fetch actual ingested user data for all successfully processed items in a job."""
    try:
        conn = await asyncpg.connect(settings.asyncpg_dsn)
        try:
            job = await conn.fetchrow(
                "SELECT id, platform FROM ingest_job WHERE id = $1 AND is_deleted = FALSE",
                job_id,
            )
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")

            platform = job["platform"]

            # Get logins of successfully processed items
            items = await conn.fetch(
                "SELECT login FROM ingest_job_item "
                "WHERE job_id = $1 AND status = 'success' "
                "ORDER BY created_at LIMIT $2 OFFSET $3",
                job_id,
                limit,
                offset,
            )

            results = []
            for item in items:
                login = item["login"]
                if platform == "github":
                    data = await _fetch_gh_user_data(conn, login)
                else:
                    data = await _fetch_hf_user_data(conn, login)
                results.append(data)
        finally:
            await conn.close()

        return success_response(results)
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), 500)


@router.get("/jobs/{job_id}/data/{login}", response_model=BaseResponse[dict[str, Any]])
async def get_job_user_data(job_id: str, login: str, _actor_id: str = Depends(get_actor_id_required)) -> BaseResponse:
    """Fetch full ingested data for a single user processed in a job."""
    try:
        conn = await asyncpg.connect(settings.asyncpg_dsn)
        try:
            job = await conn.fetchrow(
                "SELECT id, platform FROM ingest_job WHERE id = $1 AND is_deleted = FALSE",
                job_id,
            )
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")

            # Verify this login was part of the job
            item = await conn.fetchrow(
                "SELECT id, job_id, login, platform, status, attempt_number, "
                "started_at, completed_at, duration_ms, records_written, "
                "error_type, error_message, created_at, updated_at "
                "FROM ingest_job_item WHERE job_id = $1 AND login = $2",
                job_id,
                login,
            )
            if not item:
                raise HTTPException(
                    status_code=404, detail=f"Login '{login}' not found in job"
                )

            platform = job["platform"]
            if platform == "github":
                data = await _fetch_gh_user_data(conn, login)
            else:
                data = await _fetch_hf_user_data(conn, login)

            # Include item tracking info
            data["_job_item"] = _serialize_row(dict(item))
        finally:
            await conn.close()

        return success_response(data)
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), 500)
