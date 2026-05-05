"""API endpoints for GH/HF/LN discovery and ingestion."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict

import asyncpg
from fastapi import APIRouter, BackgroundTasks

from app.api.tags import Tags
from app.api.v1.request.ingest_request import (
    GHDiscoverRequest,
    GHFilterRequest,
    HFDiscoverRequest,
    IngestRequest,
    LNIngestRequest,
    ManualProfileRequest,
)
from app.api.v1.response.base_response import BaseResponse, success_response
from app.api.v1.response.ingest_response import GHFilterResponse, JobStartedResponse
from app.common.enum.ingest import IngestJobType, IngestTrigger
from app.settings import settings

router = APIRouter(prefix="/ingest", tags=[Tags.Ingestion])

log = logging.getLogger(__name__)


# ---- GitHub endpoints ----


@router.post("/gh/discover", response_model=BaseResponse[JobStartedResponse])
async def gh_discover(
    req: GHDiscoverRequest, background_tasks: BackgroundTasks
) -> BaseResponse:
    pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
    try:
        from app.ingest.common.job_tracker import JobTracker

        tracker = JobTracker(pool, "github")
        job_id = await tracker.create_job(
            job_type=IngestJobType.GH_DISCOVER,
            trigger=IngestTrigger.API,
            input_params={
                "top": req.top, "alpha": req.alpha, "org": req.org,
                "languages": req.languages, "topics": req.topics,
                "min_followers": req.min_followers, "min_repos": req.min_repos,
            },
        )
    finally:
        await pool.close()

    # Check if org was recently fetched — skip if within refresh window
    if req.org:
        from app.ingest.gh.storage import GHStorage

        check_storage = GHStorage(settings.asyncpg_dsn, pool_min=1, pool_max=2)
        await check_storage.connect()
        try:
            if await check_storage.is_org_fetched(req.org, settings.gh_refresh_after_hours):
                return success_response({
                    "job_id": job_id,
                    "status": "skipped",
                    "message": f"org '{req.org}' already fetched within {settings.gh_refresh_after_hours}h refresh window",
                })
        finally:
            await check_storage.close()

    async def _run_with_id() -> None:
        try:
            from app.ingest.common.job_tracker import JobTracker
            from app.ingest.gh.config import GHConfig
            from app.ingest.gh.discover import discover_top_users
            from app.ingest.gh.storage import GHStorage

            config = GHConfig()
            config.validate()

            storage = GHStorage(config.db_dsn, config.db_pool_min, config.db_pool_max)
            await storage.connect()
            try:
                tracker = JobTracker(storage.pool, "github")
                tracker._job_id = job_id
                await tracker.mark_running()

                ranked = await discover_top_users(
                    config, n=req.top, alpha=req.alpha,
                    org=req.org, languages=req.languages, topics=req.topics,
                    min_followers=req.min_followers, min_repos=req.min_repos,
                    storage=storage, job_id=job_id,
                )
                await tracker.mark_completed({
                    "processed": len(ranked),
                    "succeeded": len(ranked),
                    "failed": 0,
                    "skipped": 0,
                    "total": len(ranked),
                })
            finally:
                await storage.close()
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


@router.post("/gh/run", response_model=BaseResponse[JobStartedResponse])
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


# ---- GitHub post-ingest filter (synchronous — queries already-ingested data) ----


@router.post("/gh/filter", response_model=BaseResponse[GHFilterResponse])
async def gh_filter(req: GHFilterRequest) -> BaseResponse:
    """Query already-ingested GitHub users by activity and profile criteria.

    Returns logins + stats for users matching all filters. The logins list
    can be fed directly into POST /gh/run to trigger full profile ingestion.
    """
    pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=3)
    try:
        conditions: list[str] = []
        params: list = [req.days, req.min_commits]  # $1=days, $2=min_commits (used in CTEs)
        idx = 3

        if req.min_followers is not None:
            conditions.append(f"u.followers >= ${idx}")
            params.append(req.min_followers)
            idx += 1

        if req.min_repos is not None:
            conditions.append(f"u.public_repos >= ${idx}")
            params.append(req.min_repos)
            idx += 1

        if req.min_stars is not None:
            conditions.append(f"COALESCE(ra.total_stars, 0) >= ${idx}")
            params.append(req.min_stars)
            idx += 1

        if req.company:
            conditions.append(f"u.company ILIKE ${idx}")
            params.append(f"%{req.company}%")
            idx += 1

        if req.location:
            conditions.append(f"u.location ILIKE ${idx}")
            params.append(f"%{req.location}%")
            idx += 1

        if req.languages:
            conditions.append(f"ra.languages && ${idx}::text[]")
            params.append(req.languages)
            idx += 1

        params.append(req.limit)
        limit_idx = idx

        where_clause = ("AND " + " AND ".join(conditions)) if conditions else ""

        sql = f"""
            WITH recent_commits AS (
                SELECT author_login, COUNT(*) AS commit_count
                FROM gh_commits
                WHERE committed_at >= NOW() - ($1 * INTERVAL '1 day')
                GROUP BY author_login
                HAVING COUNT(*) >= $2
            ),
            repo_agg AS (
                SELECT
                    r.owner_id,
                    COALESCE(SUM(r.stars), 0) AS total_stars,
                    ARRAY_AGG(DISTINCT r.primary_language)
                        FILTER (WHERE r.primary_language IS NOT NULL) AS languages
                FROM gh_repositories r
                GROUP BY r.owner_id
            )
            SELECT
                u.login,
                u.followers,
                u.public_repos,
                u.company,
                u.location,
                COALESCE(ra.total_stars, 0) AS total_stars,
                COALESCE(ra.languages, ARRAY[]::text[]) AS languages,
                rc.commit_count
            FROM gh_users u
            JOIN recent_commits rc ON rc.author_login = u.login
            LEFT JOIN repo_agg ra ON ra.owner_id = u.id
            {where_clause}
            ORDER BY rc.commit_count DESC
            LIMIT ${limit_idx}
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        users = [
            {
                "login": r["login"],
                "followers": r["followers"],
                "public_repos": r["public_repos"],
                "company": r["company"],
                "location": r["location"],
                "total_stars": r["total_stars"],
                "languages": list(r["languages"] or []),
                "commit_count": r["commit_count"],
            }
            for r in rows
        ]
        return success_response({
            "total": len(users),
            "logins": [u["login"] for u in users],
            "users": users,
        })
    finally:
        await pool.close()


# ---- HuggingFace endpoints ----


@router.post("/hf/discover", response_model=BaseResponse[JobStartedResponse])
async def hf_discover(
    req: HFDiscoverRequest, background_tasks: BackgroundTasks
) -> BaseResponse:
    pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
    try:
        from app.ingest.common.job_tracker import JobTracker

        tracker = JobTracker(pool, "huggingface")
        job_id = await tracker.create_job(
            job_type=IngestJobType.HF_DISCOVER,
            trigger=IngestTrigger.API,
            input_params={
                "top": req.top, "alpha": req.alpha,
                "pipeline_tag": req.pipeline_tag, "library": req.library,
            },
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

                ranked = await discover_top_authors(
                    config, n=req.top, alpha=req.alpha,
                    pipeline_tag=req.pipeline_tag, library=req.library,
                )
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


@router.post("/hf/run", response_model=BaseResponse[JobStartedResponse])
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


# ---- LinkedIn endpoints ----


@router.post("/ln/discover", response_model=BaseResponse[JobStartedResponse])
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


@router.post("/ln/run", response_model=BaseResponse[JobStartedResponse])
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


# ---- Manual profile ingest ----


@router.post("/profile", response_model=BaseResponse[JobStartedResponse])
async def ingest_profile(
    req: ManualProfileRequest, background_tasks: BackgroundTasks
) -> BaseResponse:
    """Ingest a single person from provided platform links and run the full merge pipeline."""
    pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
    try:
        from app.ingest.common.job_tracker import JobTracker

        tracker = JobTracker(pool, "profile")
        job_id = await tracker.create_job(
            job_type=IngestJobType.PROFILE_INGEST,
            trigger=IngestTrigger.API,
            input_params={
                "name": req.name,
                "github_username": req.github_username,
                "huggingface_username": req.huggingface_username,
                "linkedin_url": req.linkedin_url,
            },
        )
    finally:
        await pool.close()

    async def _run_manual_profile() -> None:
        try:
            from app.ingest.bridge.config import BridgeConfig
            from app.ingest.bridge.orchestrator import BridgeOrchestrator
            from app.ingest.bridge.storage import BridgeStorage
            from app.ingest.common.job_tracker import JobTracker

            # Step 1: GitHub ingest
            if req.github_username:
                from app.ingest.gh.client import GitHubClient
                from app.ingest.gh.config import GHConfig
                from app.ingest.gh.orchestrator import GHOrchestrator
                from app.ingest.gh.storage import GHStorage
                from app.ingest.gh.token_pool import TokenPool

                gh_config = GHConfig()
                gh_config.validate()
                token_pool = TokenPool(gh_config.github_tokens)
                gh_storage = GHStorage(
                    gh_config.db_dsn, gh_config.db_pool_min, gh_config.db_pool_max
                )
                await gh_storage.connect()
                try:
                    async with GitHubClient(gh_config, token_pool) as client:
                        orch = GHOrchestrator(gh_config, client, gh_storage)
                        await orch.run([req.github_username])
                finally:
                    await gh_storage.close()

            # Step 2: HuggingFace ingest
            if req.huggingface_username:
                from app.ingest.hf.client import HFClient
                from app.ingest.hf.config import HFConfig
                from app.ingest.hf.orchestrator import HFOrchestrator
                from app.ingest.hf.storage import HFStorage

                hf_config = HFConfig()
                hf_config.validate()
                hf_storage = HFStorage(
                    hf_config.db_dsn, hf_config.db_pool_min, hf_config.db_pool_max
                )
                await hf_storage.connect()
                try:
                    async with HFClient(hf_config) as client:
                        orch = HFOrchestrator(hf_config, client, hf_storage)
                        await orch.run([req.huggingface_username])
                finally:
                    await hf_storage.close()

            # Step 3: LinkedIn ingest
            if req.linkedin_url:
                from app.ingest.ln.client import ProxycurlClient
                from app.ingest.ln.config import LNConfig
                from app.ingest.ln.orchestrator import LNOrchestrator
                from app.ingest.ln.storage import LNStorage

                ln_config = LNConfig()
                ln_config.validate()
                ln_storage = LNStorage(
                    ln_config.db_dsn, ln_config.db_pool_min, ln_config.db_pool_max
                )
                await ln_storage.connect()
                try:
                    async with ProxycurlClient(ln_config) as client:
                        orch = LNOrchestrator(ln_config, client, ln_storage)
                        await orch.run(urls=[req.linkedin_url])
                finally:
                    await ln_storage.close()

            # Step 4: Bridge merge pipeline
            bridge_config = BridgeConfig()
            bridge_config.validate()
            bridge_storage = BridgeStorage(
                bridge_config.db_dsn, bridge_config.db_pool_min, bridge_config.db_pool_max
            )
            await bridge_storage.connect()
            try:
                bridge_tracker = JobTracker(bridge_storage.pool, "profile")
                bridge_tracker._job_id = job_id
                await bridge_tracker.mark_running()

                bridge_orch = BridgeOrchestrator(bridge_config, bridge_storage)
                await bridge_orch._sync_one({
                    "login": req.github_username,
                    "hf_username": req.huggingface_username,
                    "linkedin_url": req.linkedin_url,
                })

                platforms = []
                if req.github_username:
                    platforms.append("github")
                if req.huggingface_username:
                    platforms.append("huggingface")
                if req.linkedin_url:
                    platforms.append("linkedin")

                await bridge_tracker.mark_completed({
                    "processed": 1,
                    "succeeded": 1,
                    "failed": 0,
                    "skipped": 0,
                    "platforms": platforms,
                })
            finally:
                await bridge_storage.close()

        except Exception as e:
            log.exception("profile-ingest job %s failed", job_id)
            try:
                p = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
                try:
                    t = JobTracker(p, "profile")
                    t._job_id = job_id
                    await t.mark_failed(str(e))
                finally:
                    await p.close()
            except Exception:
                pass

    background_tasks.add_task(lambda: asyncio.run(_run_manual_profile()))
    return success_response({"job_id": job_id, "status": "started"})
