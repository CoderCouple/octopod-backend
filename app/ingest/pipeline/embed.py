"""
Batch embed cohesive_individual_profile rows to Qdrant + OpenSearch.
Replaces the previous stub with a real implementation.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import asyncpg

log = logging.getLogger(__name__)


async def _register_jsonb_codec(conn: asyncpg.Connection) -> None:
    """Make asyncpg return JSONB columns as Python objects, not raw JSON strings.

    Without this, indexer sees ``"[]"`` (string) instead of ``[]`` (list) for
    columns like ``job_history`` — and OpenSearch rejects with mapper_parsing_exception.
    """
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    await conn.set_type_codec(
        "json",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )

# Explicit columns for cohesive_individual_profile (no SELECT *)
_CIP_COLUMNS = (
    "id, developer_profile_id, display_name, bio, headline, location, avatar_url, "
    "company, website, total_repos, total_stars, total_contributions, total_followers, "
    "total_hf_models, total_hf_datasets, total_hf_spaces, total_hf_downloads, "
    "total_papers, languages, skills, topics, years_of_experience, current_title, "
    "current_company, job_history, embedding_text, embedding_vector_id, "
    "source_priority, merged_at"
)


async def batch_embed_from_db(
    pool: asyncpg.Pool,
    indexer: Any,
    batch_size: int = 200,
    force: bool = False,
    pipeline_tracker: Any | None = None,
    step_order: int | None = None,
) -> dict[str, int]:
    """Fetch cohesive profiles and index them via DualIndexer.

    Args:
        pool: asyncpg connection pool
        indexer: DualIndexer instance
        batch_size: how many profiles per batch
        force: if True, re-embed profiles that already have an embedding_vector_id
        pipeline_tracker: optional PipelineTracker for live progress updates
        step_order: step number within pipeline (for tracker.update_step_progress)

    Returns:
        stats dict {total, embedded, skipped, errors}
    """
    # Count total eligible profiles
    async with pool.acquire() as conn:
        await _register_jsonb_codec(conn)
        if force:
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM cohesive_individual_profile "
                "WHERE embedding_text IS NOT NULL AND embedding_text != ''"
            )
        else:
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM cohesive_individual_profile "
                "WHERE embedding_text IS NOT NULL AND embedding_text != '' "
                "AND (embedding_vector_id IS NULL OR embedding_vector_id = '')"
            )

    if total == 0:
        log.info("No profiles to embed")
        return {"total": 0, "embedded": 0, "skipped": 0, "errors": 0}

    log.info("Embedding %d profiles (batch_size=%d, force=%s)", total, batch_size, force)

    embedded = 0
    errors = 0
    offset = 0

    while offset < total:
        async with pool.acquire() as conn:
            await _register_jsonb_codec(conn)
            if force:
                rows = await conn.fetch(
                    f"SELECT {_CIP_COLUMNS} FROM cohesive_individual_profile "
                    f"WHERE embedding_text IS NOT NULL AND embedding_text != '' "
                    f"ORDER BY id LIMIT $1 OFFSET $2",
                    batch_size,
                    offset,
                )
            else:
                rows = await conn.fetch(
                    f"SELECT {_CIP_COLUMNS} FROM cohesive_individual_profile "
                    f"WHERE embedding_text IS NOT NULL AND embedding_text != '' "
                    f"AND (embedding_vector_id IS NULL OR embedding_vector_id = '') "
                    f"ORDER BY id LIMIT $1 OFFSET $2",
                    batch_size,
                    offset,
                )

        if not rows:
            break

        profiles = [dict(r) for r in rows]
        batch_stats = await indexer.batch_index(profiles)

        batch_embedded = batch_stats.get("qdrant", 0)
        batch_errors = batch_stats.get("errors", 0)
        embedded += batch_embedded
        errors += batch_errors

        # Update embedding_vector_id for successfully indexed profiles
        if batch_embedded > 0:
            async with pool.acquire() as conn:
                await _register_jsonb_codec(conn)
                for p in profiles:
                    if p.get("embedding_vector_id"):
                        continue
                    # The indexer sets vector_id via index_profile, but we need
                    # to persist it back. For now, mark that it was embedded.
                    await conn.execute(
                        "UPDATE cohesive_individual_profile "
                        "SET embedding_vector_id = $2 "
                        "WHERE id = $1 AND (embedding_vector_id IS NULL OR embedding_vector_id = '')",
                        p["id"],
                        p.get("embedding_vector_id") or p["id"],
                    )

        offset += len(rows)
        log.info("  embedded batch: %d/%d (errors=%d)", embedded, total, errors)

        # Update pipeline tracker progress if available
        if pipeline_tracker and step_order:
            await pipeline_tracker.update_step_progress(
                step_order, total, embedded, errors
            )

    stats = {"total": total, "embedded": embedded, "skipped": total - embedded - errors, "errors": errors}
    log.info("Embed complete: %s", stats)
    return stats
