"""Postgres storage for HF data; mirrors gh storage patterns."""
from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import datetime
from typing import Any

import asyncpg

log = logging.getLogger(__name__)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_languages(tags: list[str]) -> list[str]:
    """HF tags include language tags like 'language:en', 'language:zh'."""
    return [t.split(":", 1)[1] for t in (tags or []) if t.startswith("language:")]


def _split_id(full_id: str) -> tuple[str, str]:
    """'openai/whisper-large' -> ('openai', 'whisper-large')."""
    if "/" in full_id:
        owner, name = full_id.split("/", 1)
        return owner, name
    return "", full_id


def _coerce_list(value: Any) -> list[str]:
    """Card data can be str, list, or None. Normalize to list of str."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return []


class HFStorage:
    def __init__(self, dsn: str, pool_min: int = 2, pool_max: int = 10) -> None:
        self.dsn = dsn
        self.pool_min = pool_min
        self.pool_max = pool_max
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            self.dsn, min_size=self.pool_min, max_size=self.pool_max
        )

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    @property
    def pool(self) -> asyncpg.Pool:
        if not self._pool:
            raise RuntimeError("HFStorage not connected")
        return self._pool

    async def init_schema(self, sql: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(sql)

    # ---------- Upserts ----------

    async def upsert_user(self, username: str, user: dict[str, Any]) -> str:
        user_type = user.get("_type", "user")
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO hf_users (
                    username, type, fullname, avatar_url, is_pro,
                    num_models, num_datasets, num_followers, num_following,
                    num_likes, bio, website_url, twitter, github_username,
                    linkedin, created_at, raw
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
                ON CONFLICT (username) DO UPDATE SET
                    type = EXCLUDED.type,
                    fullname = EXCLUDED.fullname,
                    avatar_url = EXCLUDED.avatar_url,
                    is_pro = EXCLUDED.is_pro,
                    num_models = EXCLUDED.num_models,
                    num_datasets = EXCLUDED.num_datasets,
                    num_followers = EXCLUDED.num_followers,
                    num_following = EXCLUDED.num_following,
                    num_likes = EXCLUDED.num_likes,
                    bio = EXCLUDED.bio,
                    website_url = EXCLUDED.website_url,
                    twitter = EXCLUDED.twitter,
                    github_username = EXCLUDED.github_username,
                    linkedin = EXCLUDED.linkedin,
                    ingested_at = NOW(),
                    raw = EXCLUDED.raw
                """,
                username,
                user_type,
                user.get("fullname") or user.get("name"),
                user.get("avatarUrl"),
                user.get("isPro"),
                user.get("numModels", 0) or 0,
                user.get("numDatasets", 0) or 0,
                user.get("numFollowers"),
                user.get("numFollowing"),
                user.get("numLikes"),
                user.get("details") or user.get("bio"),
                user.get("websiteUrl"),
                user.get("twitter") or user.get("twitterUsername"),
                user.get("githubUsername") or user.get("github"),
                user.get("linkedinUsername") or user.get("linkedin"),
                _parse_ts(user.get("createdAt")),
                json.dumps(user),
            )
        return username

    async def upsert_models(
        self, author: str, models: Iterable[dict[str, Any]]
    ) -> int:
        rows = []
        for m in models:
            if not m or not m.get("id"):
                continue
            full_id = m["id"]
            _, name = _split_id(full_id)
            card = m.get("cardData") or {}
            tags = m.get("tags") or []
            rows.append((
                full_id,
                author,
                name,
                m.get("pipeline_tag"),
                m.get("library_name"),
                card.get("license") or m.get("license"),
                card.get("base_model") if isinstance(card.get("base_model"), str) else None,
                m.get("downloads", 0) or 0,
                m.get("downloadsAllTime"),
                m.get("likes", 0) or 0,
                bool(m.get("private")),
                bool(m.get("gated")),
                bool(m.get("disabled")),
                tags,
                _extract_languages(tags),
                _coerce_list(card.get("datasets")),
                _parse_ts(m.get("createdAt")),
                _parse_ts(m.get("lastModified")),
                m.get("sha"),
                json.dumps(card),
                json.dumps(m),
            ))
        if not rows:
            return 0
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(
                    """
                    INSERT INTO hf_models (
                        id, author, name, pipeline_tag, library_name, license,
                        base_model, downloads_30d, downloads_all, likes,
                        is_private, is_gated, is_disabled, tags, languages,
                        datasets_used, created_at, last_modified, sha, card_data, raw
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21)
                    ON CONFLICT (id) DO UPDATE SET
                        pipeline_tag = EXCLUDED.pipeline_tag,
                        library_name = EXCLUDED.library_name,
                        license = EXCLUDED.license,
                        base_model = EXCLUDED.base_model,
                        downloads_30d = EXCLUDED.downloads_30d,
                        downloads_all = EXCLUDED.downloads_all,
                        likes = EXCLUDED.likes,
                        is_private = EXCLUDED.is_private,
                        is_gated = EXCLUDED.is_gated,
                        is_disabled = EXCLUDED.is_disabled,
                        tags = EXCLUDED.tags,
                        languages = EXCLUDED.languages,
                        datasets_used = EXCLUDED.datasets_used,
                        last_modified = EXCLUDED.last_modified,
                        sha = EXCLUDED.sha,
                        card_data = EXCLUDED.card_data,
                        ingested_at = NOW(),
                        raw = EXCLUDED.raw
                    """,
                    rows,
                )
        return len(rows)

    async def upsert_datasets(
        self, author: str, datasets: Iterable[dict[str, Any]]
    ) -> int:
        rows = []
        for d in datasets:
            if not d or not d.get("id"):
                continue
            full_id = d["id"]
            _, name = _split_id(full_id)
            card = d.get("cardData") or {}
            tags = d.get("tags") or []
            size_cat = None
            for t in tags:
                if t.startswith("size_categories:"):
                    size_cat = t.split(":", 1)[1]
                    break
            rows.append((
                full_id,
                author,
                name,
                _coerce_list(card.get("task_categories")),
                card.get("license") or d.get("license"),
                size_cat,
                d.get("downloads", 0) or 0,
                d.get("likes", 0) or 0,
                bool(d.get("private")),
                bool(d.get("gated")),
                bool(d.get("disabled")),
                tags,
                _extract_languages(tags),
                _parse_ts(d.get("createdAt")),
                _parse_ts(d.get("lastModified")),
                d.get("sha"),
                json.dumps(card),
                json.dumps(d),
            ))
        if not rows:
            return 0
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(
                    """
                    INSERT INTO hf_datasets (
                        id, author, name, task_categories, license, size_category,
                        downloads_30d, likes, is_private, is_gated, is_disabled,
                        tags, languages, created_at, last_modified, sha, card_data, raw
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)
                    ON CONFLICT (id) DO UPDATE SET
                        task_categories = EXCLUDED.task_categories,
                        license = EXCLUDED.license,
                        size_category = EXCLUDED.size_category,
                        downloads_30d = EXCLUDED.downloads_30d,
                        likes = EXCLUDED.likes,
                        is_private = EXCLUDED.is_private,
                        is_gated = EXCLUDED.is_gated,
                        is_disabled = EXCLUDED.is_disabled,
                        tags = EXCLUDED.tags,
                        languages = EXCLUDED.languages,
                        last_modified = EXCLUDED.last_modified,
                        sha = EXCLUDED.sha,
                        card_data = EXCLUDED.card_data,
                        ingested_at = NOW(),
                        raw = EXCLUDED.raw
                    """,
                    rows,
                )
        return len(rows)

    # ---------- Checkpoints ----------

    async def mark_checkpoint(
        self, username: str, status: str, error: str | None = None, job_id: str | None = None
    ) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO hf_checkpoints (
                    username, status, last_attempt, last_success, last_error, attempt_count, last_job_id
                ) VALUES ($1, $2, NOW(),
                          CASE WHEN $2 = 'success' THEN NOW() ELSE NULL END,
                          $3, 1, $4)
                ON CONFLICT (username) DO UPDATE SET
                    status = EXCLUDED.status,
                    last_attempt = NOW(),
                    last_success = CASE WHEN EXCLUDED.status = 'success'
                                        THEN NOW() ELSE hf_checkpoints.last_success END,
                    last_error = EXCLUDED.last_error,
                    attempt_count = hf_checkpoints.attempt_count + 1,
                    last_job_id = COALESCE(EXCLUDED.last_job_id, hf_checkpoints.last_job_id)
                """,
                username, status, error, job_id,
            )

    async def recently_ingested(self, username: str, within_hours: int) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 1 FROM hf_checkpoints
                WHERE username = $1 AND status = 'success'
                  AND last_success > NOW() - make_interval(hours => $2)
                """,
                username, within_hours,
            )
        return row is not None
