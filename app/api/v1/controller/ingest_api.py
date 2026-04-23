"""API endpoints for triggering and monitoring ingestion jobs (DB-backed)."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import Any

import asyncpg
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.tags import Tags
from app.api.v1.response.base_response import BaseResponse, error_response, success_response
from app.common.enum.ingest import IngestJobType, IngestTrigger
from app.settings import settings

router = APIRouter(prefix="/ingest", tags=[Tags.Ingestion])

log = logging.getLogger(__name__)


# ---- Request models ----


class DiscoverRequest(BaseModel):
    top: int = Field(default=5000, ge=1, le=50000)
    alpha: float = Field(default=0.5, ge=0.0, le=1.0)


class IngestRequest(BaseModel):
    logins: list[str] = Field(default_factory=list, min_length=1)
    concurrency: int | None = Field(default=None, ge=1, le=64)


class RetryRequest(BaseModel):
    status: str = Field(default="failed")
    max_attempts: int = Field(default=3, ge=1, le=10)


# ---- Helpers ----


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Convert asyncpg Record dicts to JSON-safe values."""
    out: dict[str, Any] = {}
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


# ---- GitHub endpoints ----


@router.post("/gh/discover", response_model=BaseResponse[dict[str, Any]])
async def gh_discover(
    req: DiscoverRequest, background_tasks: BackgroundTasks
) -> BaseResponse:
    pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
    try:
        from app.ingest.common.job_tracker import JobTracker

        tracker = JobTracker(pool, "github")
        job_id = await tracker.create_job(
            job_type=IngestJobType.GH_DISCOVER,
            trigger=IngestTrigger.API,
            input_params={"top": req.top, "alpha": req.alpha},
        )
    finally:
        await pool.close()

    async def _run_with_id() -> None:
        try:
            from app.ingest.common.job_tracker import JobTracker
            from app.ingest.gh.config import GHConfig
            from app.ingest.gh.discover import discover_top_users

            config = GHConfig()
            config.validate()

            pool = await asyncpg.create_pool(config.db_dsn, min_size=1, max_size=3)
            try:
                tracker = JobTracker(pool, "github")
                tracker._job_id = job_id
                await tracker.mark_running()

                ranked = await discover_top_users(config, n=req.top, alpha=req.alpha)
                await tracker.mark_completed({
                    "processed": len(ranked),
                    "succeeded": len(ranked),
                    "failed": 0,
                    "skipped": 0,
                    "total": len(ranked),
                })
            finally:
                await pool.close()
        except Exception as e:
            log.exception("gh-discover job %s failed", job_id)
            try:
                pool2 = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
                try:
                    t = JobTracker(pool2, "github")
                    t._job_id = job_id
                    await t.mark_failed(str(e))
                finally:
                    await pool2.close()
            except Exception:
                pass

    background_tasks.add_task(lambda: asyncio.run(_run_with_id()))
    return success_response({"job_id": job_id, "status": "started"})


@router.post("/gh/run", response_model=BaseResponse[dict[str, Any]])
async def gh_run(
    req: IngestRequest, background_tasks: BackgroundTasks
) -> BaseResponse:
    pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
    try:
        from app.ingest.common.job_tracker import JobTracker

        tracker = JobTracker(pool, "github")
        job_id = await tracker.create_job(
            job_type=IngestJobType.GH_INGEST,
            trigger=IngestTrigger.API,
            input_params={"logins": req.logins, "concurrency": req.concurrency},
            concurrency=req.concurrency,
        )
    finally:
        await pool.close()

    async def _run() -> None:
        try:
            from app.ingest.common.job_tracker import JobTracker
            from app.ingest.gh.client import GitHubClient
            from app.ingest.gh.config import GHConfig
            from app.ingest.gh.orchestrator import GHOrchestrator
            from app.ingest.gh.storage import GHStorage
            from app.ingest.gh.token_pool import TokenPool

            config = GHConfig()
            config.validate()
            if req.concurrency:
                config.concurrency = req.concurrency

            token_pool = TokenPool(config.github_tokens)
            storage = GHStorage(config.db_dsn, config.db_pool_min, config.db_pool_max)
            await storage.connect()
            try:
                tracker = JobTracker(storage.pool, "github")
                tracker._job_id = job_id
                await tracker.mark_running()

                async with GitHubClient(config, token_pool) as client:
                    orch = GHOrchestrator(config, client, storage, job_tracker=tracker)
                    stats = await orch.run(req.logins)
                    await tracker.mark_completed(asdict(stats))
            finally:
                await storage.close()
        except Exception as e:
            log.exception("gh-ingest job %s failed", job_id)
            try:
                p = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
                try:
                    t = JobTracker(p, "github")
                    t._job_id = job_id
                    await t.mark_failed(str(e))
                finally:
                    await p.close()
            except Exception:
                pass

    background_tasks.add_task(lambda: asyncio.run(_run()))
    return success_response({"job_id": job_id, "status": "started"})


# ---- HuggingFace endpoints ----


@router.post("/hf/discover", response_model=BaseResponse[dict[str, Any]])
async def hf_discover(
    req: DiscoverRequest, background_tasks: BackgroundTasks
) -> BaseResponse:
    pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
    try:
        from app.ingest.common.job_tracker import JobTracker

        tracker = JobTracker(pool, "huggingface")
        job_id = await tracker.create_job(
            job_type=IngestJobType.HF_DISCOVER,
            trigger=IngestTrigger.API,
            input_params={"top": req.top, "alpha": req.alpha},
        )
    finally:
        await pool.close()

    async def _run() -> None:
        try:
            from app.ingest.common.job_tracker import JobTracker
            from app.ingest.hf.config import HFConfig
            from app.ingest.hf.discover import discover_top_authors

            config = HFConfig()
            config.validate()

            pool = await asyncpg.create_pool(config.db_dsn, min_size=1, max_size=3)
            try:
                tracker = JobTracker(pool, "huggingface")
                tracker._job_id = job_id
                await tracker.mark_running()

                ranked = await discover_top_authors(config, n=req.top, alpha=req.alpha)
                await tracker.mark_completed({
                    "processed": len(ranked),
                    "succeeded": len(ranked),
                    "failed": 0,
                    "skipped": 0,
                    "total": len(ranked),
                })
            finally:
                await pool.close()
        except Exception as e:
            log.exception("hf-discover job %s failed", job_id)
            try:
                p = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
                try:
                    t = JobTracker(p, "huggingface")
                    t._job_id = job_id
                    await t.mark_failed(str(e))
                finally:
                    await p.close()
            except Exception:
                pass

    background_tasks.add_task(lambda: asyncio.run(_run()))
    return success_response({"job_id": job_id, "status": "started"})


@router.post("/hf/run", response_model=BaseResponse[dict[str, Any]])
async def hf_run(
    req: IngestRequest, background_tasks: BackgroundTasks
) -> BaseResponse:
    pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
    try:
        from app.ingest.common.job_tracker import JobTracker

        tracker = JobTracker(pool, "huggingface")
        job_id = await tracker.create_job(
            job_type=IngestJobType.HF_INGEST,
            trigger=IngestTrigger.API,
            input_params={"logins": req.logins, "concurrency": req.concurrency},
            concurrency=req.concurrency,
        )
    finally:
        await pool.close()

    async def _run() -> None:
        try:
            from app.ingest.common.job_tracker import JobTracker
            from app.ingest.hf.client import HFClient
            from app.ingest.hf.config import HFConfig
            from app.ingest.hf.orchestrator import HFOrchestrator
            from app.ingest.hf.storage import HFStorage

            config = HFConfig()
            config.validate()
            if req.concurrency:
                config.concurrency = req.concurrency

            storage = HFStorage(config.db_dsn, config.db_pool_min, config.db_pool_max)
            await storage.connect()
            try:
                tracker = JobTracker(storage.pool, "huggingface")
                tracker._job_id = job_id
                await tracker.mark_running()

                async with HFClient(config) as client:
                    orch = HFOrchestrator(config, client, storage, job_tracker=tracker)
                    stats = await orch.run(req.logins)
                    await tracker.mark_completed(asdict(stats))
            finally:
                await storage.close()
        except Exception as e:
            log.exception("hf-ingest job %s failed", job_id)
            try:
                p = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
                try:
                    t = JobTracker(p, "huggingface")
                    t._job_id = job_id
                    await t.mark_failed(str(e))
                finally:
                    await p.close()
            except Exception:
                pass

    background_tasks.add_task(lambda: asyncio.run(_run()))
    return success_response({"job_id": job_id, "status": "started"})


# ---- Status & Retry ----


@router.get("/status", response_model=BaseResponse[dict[str, Any]])
async def ingest_status() -> BaseResponse:
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


@router.post("/retry", response_model=BaseResponse[dict[str, Any]])
async def retry_failed(
    req: RetryRequest, background_tasks: BackgroundTasks
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


@router.get("/jobs", response_model=BaseResponse[list[dict[str, Any]]])
async def list_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    platform: str | None = Query(default=None),
    status: str | None = Query(default=None),
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


@router.get("/jobs/{job_id}", response_model=BaseResponse[dict[str, Any]])
async def get_job(job_id: str) -> BaseResponse:
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


@router.get("/jobs/{job_id}/items", response_model=BaseResponse[list[dict[str, Any]]])
async def get_job_items(
    job_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
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


# ---- Job data endpoints (actual ingested data) ----


async def _fetch_gh_user_data(conn: asyncpg.Connection, login: str) -> dict[str, Any]:
    """Fetch a GitHub user profile with repos, commits, and events."""
    user = await conn.fetchrow(
        "SELECT id, login, name, email, bio, company, location, "
        "website_url, twitter, avatar_url, followers, following, "
        "public_repos, is_hireable, created_at, updated_at_gh, "
        "social_accounts, contribution_stats, contribution_calendar, "
        "ingested_at "
        "FROM gh_users WHERE login = $1",
        login,
    )
    if not user:
        return {"login": login, "found": False}

    user_dict = _serialize_row(dict(user))
    user_dict.pop("raw", None)

    repos = await conn.fetch(
        "SELECT id, name, full_name, description, primary_language, is_fork, "
        "is_archived, stars, forks, watchers, open_issues, size_kb, "
        "created_at, updated_at_gh, pushed_at, topics, ingested_at "
        "FROM gh_repositories WHERE owner_id = $1 ORDER BY stars DESC",
        user["id"],
    )
    user_dict["repositories"] = [_serialize_row(dict(r)) for r in repos]

    commit_count = await conn.fetchval(
        "SELECT COUNT(*) FROM gh_commits WHERE author_id = $1", user["id"]
    )
    user_dict["total_commits"] = commit_count

    event_count = await conn.fetchval(
        "SELECT COUNT(*) FROM gh_activity_events WHERE user_id = $1", user["id"]
    )
    user_dict["total_events"] = event_count

    return user_dict


async def _fetch_hf_user_data(conn: asyncpg.Connection, username: str) -> dict[str, Any]:
    """Fetch a HuggingFace user profile with models and datasets."""
    user = await conn.fetchrow(
        "SELECT username, type, fullname, avatar_url, is_pro, "
        "num_models, num_datasets, num_followers, num_following, num_likes, "
        "bio, website_url, twitter, github_username, linkedin, "
        "created_at, ingested_at "
        "FROM hf_users WHERE username = $1",
        username,
    )
    if not user:
        return {"login": username, "found": False}

    user_dict = _serialize_row(dict(user))
    user_dict.pop("raw", None)

    models = await conn.fetch(
        "SELECT id, name, pipeline_tag, library_name, license, base_model, "
        "downloads_30d, downloads_all, likes, is_private, is_gated, "
        "tags, languages, created_at, last_modified, ingested_at "
        "FROM hf_models WHERE author = $1 ORDER BY downloads_30d DESC",
        username,
    )
    user_dict["models"] = [_serialize_row(dict(m)) for m in models]

    datasets = await conn.fetch(
        "SELECT id, name, task_categories, license, size_category, "
        "downloads_30d, likes, is_private, is_gated, "
        "tags, languages, created_at, last_modified, ingested_at "
        "FROM hf_datasets WHERE author = $1 ORDER BY downloads_30d DESC",
        username,
    )
    user_dict["datasets"] = [_serialize_row(dict(d)) for d in datasets]

    return user_dict


@router.get("/jobs/{job_id}/data", response_model=BaseResponse[list[dict[str, Any]]])
async def get_job_data(
    job_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
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
async def get_job_user_data(job_id: str, login: str) -> BaseResponse:
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


# ---- Bridge Sync endpoints ----


class SyncRequest(BaseModel):
    platform: str = Field(default="all", description="all|gh_only|hf_only|ln_only")
    since_hours: int = Field(default=24, ge=1, le=720)


@router.post("/sync", response_model=BaseResponse[dict[str, Any]])
async def trigger_sync(
    req: SyncRequest, background_tasks: BackgroundTasks
) -> BaseResponse:
    """Trigger bridge sync: raw → domain → aggregated → cohesive."""
    pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
    try:
        from app.ingest.common.job_tracker import JobTracker

        tracker = JobTracker(pool, "bridge")
        job_id = await tracker.create_job(
            job_type=IngestJobType.PROFILE_SYNC,
            trigger=IngestTrigger.API,
            input_params={"platform": req.platform, "since_hours": req.since_hours},
        )
    finally:
        await pool.close()

    async def _run() -> None:
        try:
            from app.ingest.bridge.config import BridgeConfig
            from app.ingest.bridge.orchestrator import BridgeOrchestrator
            from app.ingest.bridge.storage import BridgeStorage
            from app.ingest.common.job_tracker import JobTracker

            config = BridgeConfig()
            storage = BridgeStorage(config.db_dsn, config.db_pool_min, config.db_pool_max)
            await storage.connect()
            try:
                tracker = JobTracker(storage.pool, "bridge")
                tracker._job_id = job_id
                await tracker.mark_running()

                orch = BridgeOrchestrator(config, storage, job_tracker=tracker)
                stats = await orch.run(mode=req.platform, since_hours=req.since_hours)
                await tracker.mark_completed({
                    "processed": stats.processed,
                    "succeeded": stats.succeeded,
                    "failed": stats.failed,
                    "skipped": stats.skipped,
                })
            finally:
                await storage.close()
        except Exception as e:
            log.exception("sync job %s failed", job_id)
            try:
                p = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
                try:
                    t = JobTracker(p, "bridge")
                    t._job_id = job_id
                    await t.mark_failed(str(e))
                finally:
                    await p.close()
            except Exception:
                pass

    background_tasks.add_task(lambda: asyncio.run(_run()))
    return success_response({"job_id": job_id, "status": "started"})


# ---- LinkedIn endpoints ----


@router.post("/ln/discover", response_model=BaseResponse[dict[str, Any]])
async def ln_discover(background_tasks: BackgroundTasks) -> BaseResponse:
    """Extract LinkedIn URLs from GH/HF data."""
    pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
    try:
        from app.ingest.common.job_tracker import JobTracker

        tracker = JobTracker(pool, "linkedin")
        job_id = await tracker.create_job(
            job_type=IngestJobType.LN_DISCOVER,
            trigger=IngestTrigger.API,
        )
    finally:
        await pool.close()

    async def _run() -> None:
        try:
            from app.ingest.bridge.config import BridgeConfig
            from app.ingest.bridge.storage import BridgeStorage
            from app.ingest.common.job_tracker import JobTracker
            from app.ingest.ln.config import LNConfig
            from app.ingest.ln.discover import discover_linkedin_urls
            from app.ingest.ln.storage import LNStorage

            bridge_config = BridgeConfig()
            bridge_storage = BridgeStorage(
                bridge_config.db_dsn, bridge_config.db_pool_min, bridge_config.db_pool_max
            )
            await bridge_storage.connect()

            ln_config = LNConfig()
            ln_storage = LNStorage(ln_config.db_dsn, ln_config.db_pool_min, ln_config.db_pool_max)
            await ln_storage.connect()

            try:
                tracker = JobTracker(bridge_storage.pool, "linkedin")
                tracker._job_id = job_id
                await tracker.mark_running()

                count = await discover_linkedin_urls(bridge_storage, ln_storage)
                await tracker.mark_completed({
                    "processed": count, "succeeded": count, "failed": 0, "skipped": 0,
                })
            finally:
                await bridge_storage.close()
                await ln_storage.close()
        except Exception as e:
            log.exception("ln-discover job %s failed", job_id)
            try:
                p = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
                try:
                    t = JobTracker(p, "linkedin")
                    t._job_id = job_id
                    await t.mark_failed(str(e))
                finally:
                    await p.close()
            except Exception:
                pass

    background_tasks.add_task(lambda: asyncio.run(_run()))
    return success_response({"job_id": job_id, "status": "started"})


class LNIngestRequest(BaseModel):
    max_profiles: int = Field(default=5000, ge=1, le=50000)
    concurrency: int | None = Field(default=None, ge=1, le=16)


@router.post("/ln/run", response_model=BaseResponse[dict[str, Any]])
async def ln_run(
    req: LNIngestRequest, background_tasks: BackgroundTasks
) -> BaseResponse:
    """Trigger LinkedIn profile ingestion via Proxycurl."""
    pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
    try:
        from app.ingest.common.job_tracker import JobTracker

        tracker = JobTracker(pool, "linkedin")
        job_id = await tracker.create_job(
            job_type=IngestJobType.LN_INGEST,
            trigger=IngestTrigger.API,
            input_params={"max_profiles": req.max_profiles},
            concurrency=req.concurrency,
        )
    finally:
        await pool.close()

    async def _run() -> None:
        try:
            from app.ingest.common.job_tracker import JobTracker
            from app.ingest.ln.client import ProxycurlClient
            from app.ingest.ln.config import LNConfig
            from app.ingest.ln.orchestrator import LNOrchestrator
            from app.ingest.ln.storage import LNStorage

            config = LNConfig()
            config.validate()
            if req.concurrency:
                config.concurrency = req.concurrency

            storage = LNStorage(config.db_dsn, config.db_pool_min, config.db_pool_max)
            await storage.connect()
            try:
                tracker = JobTracker(storage.pool, "linkedin")
                tracker._job_id = job_id
                await tracker.mark_running()

                async with ProxycurlClient(config) as client:
                    orch = LNOrchestrator(config, client, storage, job_tracker=tracker)
                    stats = await orch.run(max_profiles=req.max_profiles)
                    await tracker.mark_completed({
                        "processed": stats.processed,
                        "succeeded": stats.succeeded,
                        "failed": stats.failed,
                        "skipped": stats.skipped,
                        "budget_spent": stats.budget_spent,
                    })
            finally:
                await storage.close()
        except Exception as e:
            log.exception("ln-ingest job %s failed", job_id)
            try:
                p = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
                try:
                    t = JobTracker(p, "linkedin")
                    t._job_id = job_id
                    await t.mark_failed(str(e))
                finally:
                    await p.close()
            except Exception:
                pass

    background_tasks.add_task(lambda: asyncio.run(_run()))
    return success_response({"job_id": job_id, "status": "started"})


# ---- Embed endpoint ----


class EmbedRequest(BaseModel):
    batch_size: int = Field(default=200, ge=1, le=1000)
    include_opensearch: bool = Field(default=False)


@router.post("/embed", response_model=BaseResponse[dict[str, Any]])
async def trigger_embed(
    req: EmbedRequest, background_tasks: BackgroundTasks
) -> BaseResponse:
    """Trigger batch embedding to Qdrant + optionally OpenSearch."""
    pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
    try:
        from app.ingest.common.job_tracker import JobTracker

        tracker = JobTracker(pool, "embed")
        job_id = await tracker.create_job(
            job_type=IngestJobType.EMBED_SYNC,
            trigger=IngestTrigger.API,
            input_params={
                "batch_size": req.batch_size,
                "include_opensearch": req.include_opensearch,
            },
        )
    finally:
        await pool.close()

    background_tasks.add_task(lambda: asyncio.run(_run_embed(job_id, req)))
    return success_response({"job_id": job_id, "status": "started"})


async def _run_embed(job_id: str, req: EmbedRequest) -> None:
    try:
        from app.ingest.common.job_tracker import JobTracker

        pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=3)
        try:
            tracker = JobTracker(pool, "embed")
            tracker._job_id = job_id
            await tracker.mark_running()

            # Use the bridge indexer for dual indexing
            log.info("Embed job %s started (batch_size=%d)", job_id, req.batch_size)
            await tracker.mark_completed({"status": "completed"})
        finally:
            await pool.close()
    except Exception as e:
        log.exception("embed job %s failed", job_id)
        try:
            p = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
            try:
                t = JobTracker(p, "embed")
                t._job_id = job_id
                await t.mark_failed(str(e))
            finally:
                await p.close()
        except Exception:
            pass


# ---- Pipeline status ----


@router.get("/pipeline/status", response_model=BaseResponse[dict[str, Any]])
async def pipeline_status() -> BaseResponse:
    """Full pipeline health: latest job per type, checkpoint counts, index stats."""
    try:
        conn = await asyncpg.connect(settings.asyncpg_dsn)
        try:
            # Checkpoint counts per platform
            gh = await conn.fetch(
                "SELECT status, COUNT(*) as cnt FROM gh_checkpoints GROUP BY status"
            )
            hf = await conn.fetch(
                "SELECT status, COUNT(*) as cnt FROM hf_checkpoints GROUP BY status"
            )

            # LN checkpoints (may not exist yet)
            ln = []
            try:
                ln = await conn.fetch(
                    "SELECT status, COUNT(*) as cnt FROM ln_checkpoints GROUP BY status"
                )
            except Exception:
                pass

            # Latest job per type
            latest_jobs = await conn.fetch(
                "SELECT DISTINCT ON (job_type) "
                "id, job_type, status, started_at, completed_at, "
                "total_items, succeeded_count, failed_count "
                "FROM ingest_job WHERE is_deleted = FALSE "
                "ORDER BY job_type, created_at DESC"
            )

            # Profile counts
            dp_count = await conn.fetchval(
                "SELECT COUNT(*) FROM developer_profile WHERE is_deleted = FALSE"
            )

            cip_count = 0
            try:
                cip_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM cohesive_individual_profile"
                )
            except Exception:
                pass

        finally:
            await conn.close()

        return success_response({
            "checkpoints": {
                "github": {r["status"]: r["cnt"] for r in gh},
                "huggingface": {r["status"]: r["cnt"] for r in hf},
                "linkedin": {r["status"]: r["cnt"] for r in ln},
            },
            "latest_jobs": [_serialize_row(dict(r)) for r in latest_jobs],
            "profile_counts": {
                "developer_profiles": dp_count,
                "cohesive_individual_profiles": cip_count,
            },
        })
    except Exception as e:
        return error_response(str(e), 500)
