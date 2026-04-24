"""API endpoints for GH/HF/LN discovery and ingestion."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict

import asyncpg
from fastapi import APIRouter, BackgroundTasks

from app.api.tags import Tags
from app.api.v1.request.ingest_request import DiscoverRequest, IngestRequest, LNIngestRequest
from app.api.v1.response.base_response import BaseResponse, success_response
from app.api.v1.response.ingest_response import JobStartedResponse
from app.common.enum.ingest import IngestJobType, IngestTrigger
from app.settings import settings

router = APIRouter(prefix="/ingest", tags=[Tags.Ingestion])

log = logging.getLogger(__name__)


# ---- GitHub endpoints ----


@router.post("/gh/discover", response_model=BaseResponse[JobStartedResponse])
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


# ---- HuggingFace endpoints ----


@router.post("/hf/discover", response_model=BaseResponse[JobStartedResponse])
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
