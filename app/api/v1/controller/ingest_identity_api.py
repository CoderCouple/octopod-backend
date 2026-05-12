"""API endpoints for identity resolution."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.api.tags import Tags
from app.api.v1.request.ingest_request import IdentityResolveRequest
from app.api.v1.response.base_response import BaseResponse, error_response, success_response
from app.api.v1.response.ingest_response import (
    IdentityStatsResponse,
    JobStartedResponse,
    MergeApproveResponse,
    MergeCandidateDetail,
    MergeCandidateSummary,
    MergeRejectResponse,
)
from app.common.auth.auth import UserContext, get_user_context
from app.common.enum.ingest import IngestJobType, IngestTrigger
from app.common.ingest_common import _serialize_row
from app.settings import settings

router = APIRouter(prefix="/ingest", tags=[Tags.Ingestion])

log = logging.getLogger(__name__)


# ---- Identity resolution endpoints ----


@router.get("/identity/candidates", response_model=BaseResponse[list[MergeCandidateSummary]])
async def identity_candidates_list(
    status: str | None = Query(default=None, description="Filter by status: pending, approved, merged, rejected"),
    min_score: float | None = Query(default=None, ge=0, le=1),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _ctx: UserContext = Depends(get_user_context),
) -> BaseResponse:
    """List merge candidates with optional filters."""
    try:
        pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
        try:
            async with pool.acquire() as conn:
                conditions = ["mc.is_deleted = FALSE"]
                params: list[Any] = []
                idx = 1

                if status:
                    conditions.append(f"mc.status = ${idx}")
                    params.append(status)
                    idx += 1
                if min_score is not None:
                    conditions.append(f"mc.confidence_score >= ${idx}")
                    params.append(min_score)
                    idx += 1

                where = " AND ".join(conditions)
                params.extend([limit, offset])

                rows = await conn.fetch(
                    f"SELECT mc.id, mc.source_profile_id, mc.target_profile_id, "
                    f"mc.confidence_score, mc.signals, mc.status, "
                    f"mc.reviewed_by, mc.reviewed_at, mc.merged_at, "
                    f"mc.created_at, mc.updated_at, "
                    f"src.display_name AS source_name, src.github_username AS source_gh, "
                    f"src.huggingface_username AS source_hf, "
                    f"tgt.display_name AS target_name, tgt.github_username AS target_gh, "
                    f"tgt.huggingface_username AS target_hf "
                    f"FROM merge_candidate mc "
                    f"LEFT JOIN developer_profile src ON src.id = mc.source_profile_id "
                    f"LEFT JOIN developer_profile tgt ON tgt.id = mc.target_profile_id "
                    f"WHERE {where} "
                    f"ORDER BY mc.confidence_score DESC, mc.created_at DESC "
                    f"LIMIT ${idx} OFFSET ${idx + 1}",
                    *params,
                )
        finally:
            await pool.close()

        return success_response([_serialize_row(dict(r)) for r in rows])
    except Exception as e:
        return error_response(str(e), 500)


@router.get("/identity/candidates/{candidate_id}", response_model=BaseResponse[MergeCandidateDetail])
async def identity_candidate_detail(candidate_id: str, _ctx: UserContext = Depends(get_user_context)) -> BaseResponse:
    """Get merge candidate detail with profile previews and signals."""
    try:
        pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
        try:
            async with pool.acquire() as conn:
                mc = await conn.fetchrow(
                    "SELECT id, source_profile_id, target_profile_id, "
                    "confidence_score, signals, status, resolved_profile_id, "
                    "reviewed_by, reviewed_at, merged_at, created_at, updated_at "
                    "FROM merge_candidate WHERE id = $1 AND is_deleted = FALSE",
                    candidate_id,
                )
                if not mc:
                    raise HTTPException(status_code=404, detail="Merge candidate not found")

                # Fetch both profiles
                source = await conn.fetchrow(
                    "SELECT id, github_username, huggingface_username, email_hint, "
                    "display_name, company, location, avatar_url, website, "
                    "total_repos, total_stars, total_hf_models, total_hf_downloads "
                    "FROM developer_profile WHERE id = $1",
                    mc["source_profile_id"],
                )
                target = await conn.fetchrow(
                    "SELECT id, github_username, huggingface_username, email_hint, "
                    "display_name, company, location, avatar_url, website, "
                    "total_repos, total_stars, total_hf_models, total_hf_downloads "
                    "FROM developer_profile WHERE id = $1",
                    mc["target_profile_id"],
                )
        finally:
            await pool.close()

        result = _serialize_row(dict(mc))
        result["source_profile"] = _serialize_row(dict(source)) if source else None
        result["target_profile"] = _serialize_row(dict(target)) if target else None
        return success_response(result)
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), 500)


@router.post("/identity/candidates/{candidate_id}/approve", response_model=BaseResponse[MergeApproveResponse])
async def identity_candidate_approve(candidate_id: str, _ctx: UserContext = Depends(get_user_context)) -> BaseResponse:
    """Approve a merge candidate and execute the merge."""
    try:
        pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=3)
        try:
            async with pool.acquire() as conn:
                mc = await conn.fetchrow(
                    "SELECT id, source_profile_id, target_profile_id, status "
                    "FROM merge_candidate WHERE id = $1 AND is_deleted = FALSE",
                    candidate_id,
                )
                if not mc:
                    raise HTTPException(status_code=404, detail="Merge candidate not found")
                if mc["status"] == "merged":
                    return error_response("Already merged", 409)
                if mc["status"] == "rejected":
                    return error_response("Candidate was rejected", 409)

                # Mark approved
                await conn.execute(
                    "UPDATE merge_candidate SET status = 'approved', "
                    "reviewed_by = 'api', reviewed_at = NOW(), updated_at = NOW() "
                    "WHERE id = $1",
                    candidate_id,
                )

            # Execute merge
            from app.ingest.bridge.storage import BridgeStorage

            storage = BridgeStorage.__new__(BridgeStorage)
            storage._pool = pool
            await storage.merge_profiles(mc["source_profile_id"], mc["target_profile_id"])
        finally:
            await pool.close()

        return success_response({
            "id": candidate_id,
            "status": "merged",
            "source_profile_id": mc["source_profile_id"],
            "target_profile_id": mc["target_profile_id"],
        })
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), 500)


@router.post("/identity/candidates/{candidate_id}/reject", response_model=BaseResponse[MergeRejectResponse])
async def identity_candidate_reject(candidate_id: str, _ctx: UserContext = Depends(get_user_context)) -> BaseResponse:
    """Reject a merge candidate."""
    try:
        pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
        try:
            async with pool.acquire() as conn:
                mc = await conn.fetchrow(
                    "SELECT id, status FROM merge_candidate "
                    "WHERE id = $1 AND is_deleted = FALSE",
                    candidate_id,
                )
                if not mc:
                    raise HTTPException(status_code=404, detail="Merge candidate not found")
                if mc["status"] == "merged":
                    return error_response("Already merged, cannot reject", 409)

                await conn.execute(
                    "UPDATE merge_candidate SET status = 'rejected', "
                    "reviewed_by = 'api', reviewed_at = NOW(), updated_at = NOW() "
                    "WHERE id = $1",
                    candidate_id,
                )
        finally:
            await pool.close()

        return success_response({"id": candidate_id, "status": "rejected"})
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), 500)


@router.post("/identity/resolve", response_model=BaseResponse[JobStartedResponse])
async def identity_resolve_trigger(
    req: IdentityResolveRequest, background_tasks: BackgroundTasks,
    _ctx: UserContext = Depends(get_user_context),
) -> BaseResponse:
    """Trigger identity resolution as a background task."""
    pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
    try:
        from app.ingest.common.job_tracker import JobTracker

        tracker = JobTracker(pool, "identity")
        job_id = await tracker.create_job(
            job_type=IngestJobType.IDENTITY_RESOLVE,
            trigger=IngestTrigger.API,
            input_params={"since_hours": req.since_hours, "full_scan": req.full_scan},
        )
    finally:
        await pool.close()

    async def _run() -> None:
        try:
            from app.ingest.bridge.resolver import IdentityResolver
            from app.ingest.common.job_tracker import JobTracker

            p = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=2, max_size=5)
            try:
                tracker = JobTracker(p, "identity")
                tracker._job_id = job_id
                await tracker.mark_running()

                resolver = IdentityResolver(p)
                stats = await resolver.run(
                    since_hours=req.since_hours, full_scan=req.full_scan
                )
                await tracker.mark_completed({
                    "total_candidates": stats.total_candidates,
                    "auto_merged": stats.auto_merged,
                    "queued_for_review": stats.queued_for_review,
                    "skipped": stats.skipped,
                    "errors": stats.errors,
                })
            finally:
                await p.close()
        except Exception as e:
            log.exception("identity-resolve job %s failed", job_id)
            try:
                p = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
                try:
                    t = JobTracker(p, "identity")
                    t._job_id = job_id
                    await t.mark_failed(str(e))
                finally:
                    await p.close()
            except Exception:
                pass

    background_tasks.add_task(lambda: asyncio.run(_run()))
    return success_response({"job_id": job_id, "status": "started"})


@router.get("/identity/stats", response_model=BaseResponse[IdentityStatsResponse])
async def identity_stats(_ctx: UserContext = Depends(get_user_context)) -> BaseResponse:
    """Get identity resolution stats: counts by status, average scores."""
    try:
        pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
        try:
            async with pool.acquire() as conn:
                status_counts = await conn.fetch(
                    "SELECT status, COUNT(*) as cnt, "
                    "AVG(confidence_score)::NUMERIC(5,4) as avg_score "
                    "FROM merge_candidate WHERE is_deleted = FALSE "
                    "GROUP BY status ORDER BY status"
                )
                total_merged = await conn.fetchval(
                    "SELECT COUNT(*) FROM developer_profile "
                    "WHERE merged_into_id IS NOT NULL"
                )
        finally:
            await pool.close()

        return success_response({
            "by_status": [
                {
                    "status": r["status"],
                    "count": r["cnt"],
                    "avg_score": float(r["avg_score"]) if r["avg_score"] else 0,
                }
                for r in status_counts
            ],
            "total_merged_profiles": total_merged or 0,
        })
    except Exception as e:
        return error_response(str(e), 500)
