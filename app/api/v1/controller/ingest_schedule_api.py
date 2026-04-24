"""API endpoints for pipeline schedule CRUD."""
from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, HTTPException

from app.api.tags import Tags
from app.api.v1.request.ingest_request import ScheduleCreateRequest, ScheduleUpdateRequest
from app.api.v1.response.base_response import BaseResponse, error_response, success_response
from app.api.v1.response.ingest_response import ScheduleDeleteResponse, ScheduleResponse
from app.common.ingest_common import _serialize_row
from app.settings import settings

router = APIRouter(prefix="/ingest", tags=[Tags.Ingestion])


# ---- Schedule CRUD endpoints ----


@router.post("/schedule", response_model=BaseResponse[ScheduleResponse])
async def schedule_create(req: ScheduleCreateRequest) -> BaseResponse:
    """Create a pipeline schedule."""
    import json
    import uuid
    from datetime import datetime, timezone

    from croniter import croniter

    if not croniter.is_valid(req.cron_expression):
        return error_response(f"Invalid cron expression: {req.cron_expression}", 400)

    now = datetime.now(timezone.utc)
    cron = croniter(req.cron_expression, now)
    next_run = cron.get_next(datetime)
    schedule_id = f"ps_{uuid.uuid4().hex[:12]}"

    try:
        pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO pipeline_schedule "
                    "(id, name, pipeline_type, input_params, cron_expression, "
                    "is_enabled, next_run_at, created_at, updated_at) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $8)",
                    schedule_id, req.name, req.pipeline_type,
                    json.dumps(req.input_params), req.cron_expression,
                    req.is_enabled, next_run, now,
                )
        finally:
            await pool.close()

        return success_response({
            "id": schedule_id,
            "name": req.name,
            "pipeline_type": req.pipeline_type,
            "cron_expression": req.cron_expression,
            "is_enabled": req.is_enabled,
            "next_run_at": next_run.isoformat(),
        })
    except Exception as e:
        return error_response(str(e), 500)


@router.get("/schedules", response_model=BaseResponse[list[ScheduleResponse]])
async def schedule_list() -> BaseResponse:
    """List all pipeline schedules."""
    try:
        pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT id, name, pipeline_type, input_params, cron_expression, "
                    "is_enabled, last_run_at, next_run_at, created_at, updated_at "
                    "FROM pipeline_schedule ORDER BY created_at DESC"
                )
        finally:
            await pool.close()

        return success_response([_serialize_row(dict(r)) for r in rows])
    except Exception as e:
        return error_response(str(e), 500)


@router.put("/schedule/{schedule_id}", response_model=BaseResponse[ScheduleResponse])
async def schedule_update(schedule_id: str, req: ScheduleUpdateRequest) -> BaseResponse:
    """Update a pipeline schedule."""
    import json
    from datetime import datetime, timezone

    from croniter import croniter

    try:
        pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
        try:
            async with pool.acquire() as conn:
                existing = await conn.fetchrow(
                    "SELECT id, cron_expression FROM pipeline_schedule WHERE id = $1",
                    schedule_id,
                )
                if not existing:
                    raise HTTPException(status_code=404, detail="Schedule not found")

                sets: list[str] = []
                vals: list[Any] = [schedule_id]
                idx = 2

                if req.name is not None:
                    sets.append(f"name = ${idx}")
                    vals.append(req.name)
                    idx += 1
                if req.pipeline_type is not None:
                    sets.append(f"pipeline_type = ${idx}")
                    vals.append(req.pipeline_type)
                    idx += 1
                if req.input_params is not None:
                    sets.append(f"input_params = ${idx}")
                    vals.append(json.dumps(req.input_params))
                    idx += 1
                if req.cron_expression is not None:
                    if not croniter.is_valid(req.cron_expression):
                        return error_response(
                            f"Invalid cron expression: {req.cron_expression}", 400
                        )
                    sets.append(f"cron_expression = ${idx}")
                    vals.append(req.cron_expression)
                    idx += 1
                    # Recompute next_run_at
                    now = datetime.now(timezone.utc)
                    cron = croniter(req.cron_expression, now)
                    next_run = cron.get_next(datetime)
                    sets.append(f"next_run_at = ${idx}")
                    vals.append(next_run)
                    idx += 1
                if req.is_enabled is not None:
                    sets.append(f"is_enabled = ${idx}")
                    vals.append(req.is_enabled)
                    idx += 1

                if not sets:
                    return error_response("No fields to update", 400)

                sets.append("updated_at = now()")
                sql = f"UPDATE pipeline_schedule SET {', '.join(sets)} WHERE id = $1"
                await conn.execute(sql, *vals)

                row = await conn.fetchrow(
                    "SELECT id, name, pipeline_type, input_params, cron_expression, "
                    "is_enabled, last_run_at, next_run_at, created_at, updated_at "
                    "FROM pipeline_schedule WHERE id = $1",
                    schedule_id,
                )
        finally:
            await pool.close()

        return success_response(_serialize_row(dict(row)))
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), 500)


@router.delete("/schedule/{schedule_id}", response_model=BaseResponse[ScheduleDeleteResponse])
async def schedule_delete(schedule_id: str) -> BaseResponse:
    """Delete a pipeline schedule."""
    try:
        pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
        try:
            async with pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM pipeline_schedule WHERE id = $1", schedule_id
                )
                if result == "DELETE 0":
                    raise HTTPException(status_code=404, detail="Schedule not found")
        finally:
            await pool.close()

        return success_response({"id": schedule_id, "deleted": True})
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), 500)
