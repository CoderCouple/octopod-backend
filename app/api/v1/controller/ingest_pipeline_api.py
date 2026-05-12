"""API endpoints for pipeline execution, sync, and embedding."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.api.tags import Tags
from app.api.v1.request.ingest_request import EmbedRequest, PipelineStartRequest, SyncRequest
from app.api.v1.response.base_response import BaseResponse, error_response, success_response
from app.api.v1.response.ingest_response import (
    JobStartedResponse,
    PipelineControlResponse,
    PipelineHealthResponse,
    PipelineRerunResponse,
    PipelineResumeResponse,
    PipelineStartedResponse,
)
from app.common.auth.auth import UserContext, get_user_context
from app.common.enum.ingest import IngestJobType, IngestTrigger
from app.common.ingest_common import _serialize_row
from app.settings import settings

router = APIRouter(prefix="/ingest", tags=[Tags.Ingestion])

log = logging.getLogger(__name__)

_FULL_PIPELINE_TYPES = {"daily", "weekly", "seed", "dependent"}


# ---- Bridge Sync endpoint ----


@router.post("/sync", response_model=BaseResponse[JobStartedResponse])
async def trigger_sync(
    req: SyncRequest, background_tasks: BackgroundTasks,
    _ctx: UserContext = Depends(get_user_context),
) -> BaseResponse:
    """Trigger bridge sync: raw -> domain -> aggregated -> cohesive."""
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


# ---- Embed endpoint ----


@router.post("/embed", response_model=BaseResponse[JobStartedResponse])
async def trigger_embed(
    req: EmbedRequest, background_tasks: BackgroundTasks,
    _ctx: UserContext = Depends(get_user_context),
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
        from app.ingest.pipeline.embed import batch_embed_from_db

        pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=3)
        try:
            tracker = JobTracker(pool, "embed")
            tracker._job_id = job_id
            await tracker.mark_running()

            from app.db.qdrant_client import get_qdrant_client
            from app.ingest.bridge.indexer import DualIndexer
            from app.service.embedding.sentence_transformer_provider import (
                SentenceTransformerProvider,
            )

            qdrant_client = get_qdrant_client()
            embedding_provider = SentenceTransformerProvider()
            opensearch_client = None
            if req.include_opensearch:
                try:
                    from app.db.opensearch_client import get_opensearch_client

                    opensearch_client = get_opensearch_client()
                except Exception:
                    log.warning("OpenSearch not available, skipping")

            indexer = DualIndexer(
                qdrant_client=qdrant_client,
                opensearch_client=opensearch_client,
                embedding_provider=embedding_provider,
            )

            stats = await batch_embed_from_db(
                pool=pool, indexer=indexer, batch_size=req.batch_size
            )
            await tracker.mark_completed({
                "processed": stats["total"],
                "succeeded": stats["embedded"],
                "failed": stats["errors"],
                "skipped": stats["skipped"],
            })
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


# ---- Pipeline execution endpoints ----


@router.post("/pipeline/start", response_model=BaseResponse[PipelineStartedResponse])
async def pipeline_start(
    req: PipelineStartRequest, background_tasks: BackgroundTasks,
    _ctx: UserContext = Depends(get_user_context),
) -> BaseResponse:
    """Start a pipeline. Full pipelines block each other; individual runs can be parallel."""
    from app.ingest.pipeline.tracker import PipelineTracker

    is_full = req.pipeline_type in _FULL_PIPELINE_TYPES
    pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
    try:
        if is_full:
            active = await PipelineTracker.get_active_executions(pool)
            running_full = [
                e for e in active
                if e["status"] == "running" and e["pipeline_type"] in _FULL_PIPELINE_TYPES
            ]
            if running_full:
                return error_response(
                    f"Full pipeline {running_full[0]['id']} is already running. "
                    "Pause or cancel it first.",
                    409,
                )
    finally:
        await pool.close()

    async def _run() -> None:
        try:
            from app.ingest.pipeline.runner import PipelineRunner

            p = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=2, max_size=5)
            try:
                runner = PipelineRunner(p)
                await runner.run(
                    pipeline_type=req.pipeline_type,
                    trigger="api",
                    triggered_by="api",
                    input_params=req.input_params,
                )
            finally:
                await p.close()
        except Exception:
            log.exception("Pipeline %s failed", req.pipeline_type)

    background_tasks.add_task(lambda: asyncio.run(_run()))
    return success_response({
        "pipeline_type": req.pipeline_type,
        "status": "started",
    })


@router.get("/pipeline/active", response_model=BaseResponse[list[dict[str, Any]]])  # dynamic execution shape
async def pipeline_active(_ctx: UserContext = Depends(get_user_context)) -> BaseResponse:
    """Get currently running/paused pipelines."""
    try:
        from app.ingest.pipeline.tracker import PipelineTracker

        pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
        try:
            executions = await PipelineTracker.get_active_executions(pool)
        finally:
            await pool.close()
        return success_response([_serialize_row(e) for e in executions])
    except Exception as e:
        return error_response(str(e), 500)


@router.get("/pipeline/{execution_id}", response_model=BaseResponse[dict[str, Any]])  # dynamic execution shape
async def pipeline_get(execution_id: str, _ctx: UserContext = Depends(get_user_context)) -> BaseResponse:
    """Full execution details with all steps + live progress counts."""
    try:
        from app.ingest.pipeline.tracker import PipelineTracker

        pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
        try:
            data = await PipelineTracker.get_execution(pool, execution_id)
        finally:
            await pool.close()

        if not data:
            raise HTTPException(status_code=404, detail="Pipeline execution not found")

        result = _serialize_row(data)
        result["steps"] = [_serialize_row(s) for s in data.get("steps", [])]
        return success_response(result)
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), 500)


@router.post("/pipeline/{execution_id}/pause", response_model=BaseResponse[PipelineControlResponse])
async def pipeline_pause(execution_id: str, _ctx: UserContext = Depends(get_user_context)) -> BaseResponse:
    """Set pause signal -- current step finishes, then execution pauses."""
    try:
        from app.ingest.pipeline.tracker import PipelineTracker

        pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
        try:
            ok = await PipelineTracker.set_control_signal(pool, execution_id, "pause")
        finally:
            await pool.close()

        if not ok:
            raise HTTPException(status_code=404, detail="No running/paused pipeline found")
        return success_response({"execution_id": execution_id, "control_signal": "pause"})
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), 500)


@router.post("/pipeline/{execution_id}/resume", response_model=BaseResponse[PipelineResumeResponse])
async def pipeline_resume(
    execution_id: str, background_tasks: BackgroundTasks,
    _ctx: UserContext = Depends(get_user_context),
) -> BaseResponse:
    """Resume a paused pipeline from the next pending step."""
    from app.ingest.pipeline.tracker import PipelineTracker

    pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
    try:
        ok = await PipelineTracker.resume_execution(pool, execution_id)
        if not ok:
            raise HTTPException(status_code=404, detail="No paused pipeline found")
        next_step = await PipelineTracker.get_next_pending_step(pool, execution_id)
        data = await PipelineTracker.get_execution(pool, execution_id)
    finally:
        await pool.close()

    if next_step is None:
        return success_response({"execution_id": execution_id, "status": "no_pending_steps"})

    if data is None:
        raise HTTPException(status_code=404, detail="Pipeline execution not found")

    async def _run() -> None:
        try:
            from app.ingest.pipeline.runner import PipelineRunner
            from app.ingest.pipeline.steps import get_steps
            from app.ingest.pipeline.tracker import PipelineTracker as PT

            p = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=2, max_size=5)
            try:
                runner = PipelineRunner(p)
                pt = PT(p)
                pt._execution_id = execution_id
                await pt.mark_execution_running()

                steps = get_steps(data["pipeline_type"])
                input_params = data.get("input_params") or {}

                for i, step_def in enumerate(steps, start=1):
                    if i < next_step:
                        continue

                    signal = await pt.check_control_signal()
                    if signal == "cancel":
                        for j in range(i, len(steps) + 1):
                            await pt.mark_step_cancelled(j)
                        await pt.mark_execution_cancelled()
                        return
                    if signal == "pause":
                        await pt.clear_control_signal()
                        await pt.mark_execution_paused()
                        return

                    await pt.mark_step_running(i)
                    try:
                        step_result = await runner._execute_step(
                            step_def["name"], input_params, pt, i,
                            data["pipeline_type"], execution_id,
                        )
                        await pt.mark_step_completed(i, step_result)
                    except Exception as exc:
                        await pt.mark_step_failed(i, str(exc))
                        await pt.mark_execution_failed(str(exc))
                        return

                await pt.mark_execution_completed()
            finally:
                await p.close()
        except Exception:
            log.exception("Pipeline resume %s failed", execution_id)

    background_tasks.add_task(lambda: asyncio.run(_run()))
    return success_response({
        "execution_id": execution_id,
        "status": "resuming",
        "from_step": next_step,
    })


@router.post("/pipeline/{execution_id}/cancel", response_model=BaseResponse[PipelineControlResponse])
async def pipeline_cancel(execution_id: str, _ctx: UserContext = Depends(get_user_context)) -> BaseResponse:
    """Set cancel signal -- current step finishes, remaining steps skip."""
    try:
        from app.ingest.pipeline.tracker import PipelineTracker

        pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
        try:
            ok = await PipelineTracker.set_control_signal(pool, execution_id, "cancel")
        finally:
            await pool.close()

        if not ok:
            raise HTTPException(status_code=404, detail="No running/paused pipeline found")
        return success_response({"execution_id": execution_id, "control_signal": "cancel"})
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), 500)


@router.post("/pipeline/{execution_id}/rerun", response_model=BaseResponse[PipelineRerunResponse])
async def pipeline_rerun(
    execution_id: str, background_tasks: BackgroundTasks,
    _ctx: UserContext = Depends(get_user_context),
) -> BaseResponse:
    """Create a new execution with the same config as a previous one."""
    from app.ingest.pipeline.tracker import PipelineTracker

    pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
    try:
        data = await PipelineTracker.get_execution(pool, execution_id)
    finally:
        await pool.close()

    if not data:
        raise HTTPException(status_code=404, detail="Pipeline execution not found")

    async def _run() -> None:
        try:
            from app.ingest.pipeline.runner import PipelineRunner

            p = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=2, max_size=5)
            try:
                runner = PipelineRunner(p)
                await runner.run(
                    pipeline_type=data["pipeline_type"],
                    trigger="api",
                    triggered_by="rerun",
                    input_params=data.get("input_params") or {},
                )
            finally:
                await p.close()
        except Exception:
            log.exception("Pipeline rerun failed (original=%s)", execution_id)

    background_tasks.add_task(lambda: asyncio.run(_run()))
    return success_response({
        "pipeline_type": data["pipeline_type"],
        "status": "started",
        "rerun_of": execution_id,
    })


# ---- Pipeline status ----


@router.get("/pipeline/status", response_model=BaseResponse[PipelineHealthResponse])
async def pipeline_status(_ctx: UserContext = Depends(get_user_context)) -> BaseResponse:
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
