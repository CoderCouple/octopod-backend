"""LinkedIn storage: upserts for ln_users, ln_checkpoints, ln_pending_urls."""
from __future__ import annotations

import json
import logging
from typing import Any

import asyncpg

log = logging.getLogger(__name__)


class LNStorage:
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
            raise RuntimeError("LNStorage not connected")
        return self._pool

    async def init_schema(self, sql: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(sql)

    # ---------- Pending URLs ----------

    async def upsert_pending_urls(
        self, urls: list[dict[str, Any]]
    ) -> int:
        """Insert or update pending LinkedIn URLs for ingestion."""
        if not urls:
            return 0
        rows = [
            (
                u["linkedin_url"],
                u["source_platform"],
                u["source_username"],
                u.get("priority", 1),
            )
            for u in urls
        ]
        async with self.pool.acquire() as conn:
            await conn.executemany(
                "INSERT INTO ln_pending_urls "
                "(linkedin_url, source_platform, source_username, priority) "
                "VALUES ($1, $2, $3, $4) "
                "ON CONFLICT (linkedin_url) DO UPDATE SET "
                "priority = LEAST(ln_pending_urls.priority, EXCLUDED.priority), "
                "updated_at = NOW()",
                rows,
            )
        return len(rows)

    async def list_pending_urls(
        self, limit: int = 1000, status: str = "pending"
    ) -> list[str]:
        """List pending LinkedIn URLs ordered by priority."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT linkedin_url FROM ln_pending_urls "
                "WHERE status = $1 "
                "ORDER BY priority ASC, created_at ASC "
                "LIMIT $2",
                status, limit,
            )
        return [r["linkedin_url"] for r in rows]

    async def mark_pending_url_status(
        self, linkedin_url: str, status: str
    ) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE ln_pending_urls SET status = $2, updated_at = NOW() "
                "WHERE linkedin_url = $1",
                linkedin_url, status,
            )

    # ---------- User profiles ----------

    async def upsert_user(
        self, linkedin_url: str, profile: dict[str, Any]
    ) -> str:
        """Upsert a LinkedIn user profile from Proxycurl data."""
        experiences = profile.get("experiences") or []
        education = profile.get("education") or []
        certifications = profile.get("certifications") or []
        skills_list = [s.get("name", s) if isinstance(s, dict) else s
                       for s in (profile.get("skills") or [])]
        languages_list = [lang.get("name", lang) if isinstance(lang, dict) else lang
                          for lang in (profile.get("languages") or [])]

        # Extract current position
        current_company = None
        current_title = None
        if experiences:
            for exp in experiences:
                if exp.get("ends_at") is None:
                    current_company = exp.get("company")
                    current_title = exp.get("title")
                    break
            if not current_company and experiences:
                current_company = experiences[0].get("company")
                current_title = experiences[0].get("title")

        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO ln_users "
                "(linkedin_url, full_name, headline, summary, city, country, "
                "profile_pic_url, current_company, current_title, industry, "
                "num_connections, experiences, education, skills, certifications, "
                "languages, raw) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17) "
                "ON CONFLICT (linkedin_url) DO UPDATE SET "
                "full_name = EXCLUDED.full_name, "
                "headline = EXCLUDED.headline, "
                "summary = EXCLUDED.summary, "
                "city = EXCLUDED.city, "
                "country = EXCLUDED.country, "
                "profile_pic_url = EXCLUDED.profile_pic_url, "
                "current_company = EXCLUDED.current_company, "
                "current_title = EXCLUDED.current_title, "
                "industry = EXCLUDED.industry, "
                "num_connections = EXCLUDED.num_connections, "
                "experiences = EXCLUDED.experiences, "
                "education = EXCLUDED.education, "
                "skills = EXCLUDED.skills, "
                "certifications = EXCLUDED.certifications, "
                "languages = EXCLUDED.languages, "
                "ingested_at = NOW(), "
                "raw = EXCLUDED.raw",
                linkedin_url,
                profile.get("full_name"),
                profile.get("headline"),
                profile.get("summary"),
                profile.get("city"),
                profile.get("country_full_name") or profile.get("country"),
                profile.get("profile_pic_url"),
                current_company,
                current_title,
                profile.get("industry"),
                profile.get("connections"),
                json.dumps(experiences),
                json.dumps(education),
                skills_list,
                json.dumps(certifications),
                languages_list,
                json.dumps(profile),
            )
        return linkedin_url

    # ---------- Checkpoints ----------

    async def mark_checkpoint(
        self, linkedin_url: str, status: str,
        error: str | None = None, job_id: str | None = None
    ) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO ln_checkpoints "
                "(linkedin_url, status, last_attempt, last_success, last_error, "
                "attempt_count, last_job_id) "
                "VALUES ($1, $2, NOW(), "
                "CASE WHEN $2 = 'success' THEN NOW() ELSE NULL END, "
                "$3, 1, $4) "
                "ON CONFLICT (linkedin_url) DO UPDATE SET "
                "status = EXCLUDED.status, "
                "last_attempt = NOW(), "
                "last_success = CASE WHEN EXCLUDED.status = 'success' "
                "                    THEN NOW() ELSE ln_checkpoints.last_success END, "
                "last_error = EXCLUDED.last_error, "
                "attempt_count = ln_checkpoints.attempt_count + 1, "
                "last_job_id = COALESCE(EXCLUDED.last_job_id, ln_checkpoints.last_job_id)",
                linkedin_url, status, error, job_id,
            )

    async def recently_ingested(self, linkedin_url: str, within_hours: int) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM ln_checkpoints "
                "WHERE linkedin_url = $1 AND status = 'success' "
                "AND last_success > NOW() - make_interval(hours => $2)",
                linkedin_url, within_hours,
            )
        return row is not None
