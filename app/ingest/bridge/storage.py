"""Bridge storage: identity resolution + upserts from raw tables.

Uses asyncpg directly (same pattern as GHStorage/HFStorage).
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg

log = logging.getLogger(__name__)


class BridgeStorage:
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
            raise RuntimeError("BridgeStorage not connected")
        return self._pool

    async def init_schema(self, sql: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(sql)

    # ---------- Discovery: list users needing sync ----------

    async def list_gh_users_to_sync(
        self, since_hours: int, batch_size: int, offset: int = 0
    ) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT login, name, email, bio, company, location, "
                "website_url, twitter, avatar_url, followers, public_repos, "
                "social_accounts, contribution_stats, ingested_at "
                "FROM gh_users "
                "WHERE ingested_at > NOW() - make_interval(hours => $1) "
                "ORDER BY ingested_at DESC "
                "LIMIT $2 OFFSET $3",
                since_hours, batch_size, offset,
            )
        return [dict(r) for r in rows]

    async def list_hf_users_to_sync(
        self, since_hours: int, batch_size: int, offset: int = 0
    ) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT username, fullname, avatar_url, bio, website_url, "
                "twitter, github_username, linkedin, num_models, num_datasets, "
                "num_followers, ingested_at "
                "FROM hf_users "
                "WHERE ingested_at > NOW() - make_interval(hours => $1) "
                "  AND type = 'user' "
                "ORDER BY ingested_at DESC "
                "LIMIT $2 OFFSET $3",
                since_hours, batch_size, offset,
            )
        return [dict(r) for r in rows]

    async def list_ln_users_to_sync(
        self, since_hours: int, batch_size: int, offset: int = 0
    ) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT linkedin_url, full_name, headline, summary, city, country, "
                "profile_pic_url, current_company, current_title, industry, "
                "num_connections, experiences, education, skills, certifications, "
                "languages, ingested_at "
                "FROM ln_users "
                "WHERE ingested_at > NOW() - make_interval(hours => $1) "
                "ORDER BY ingested_at DESC "
                "LIMIT $2 OFFSET $3",
                since_hours, batch_size, offset,
            )
        return [dict(r) for r in rows]

    # ---------- Identity resolution ----------

    async def upsert_developer_profile(
        self,
        github_username: str | None = None,
        hf_username: str | None = None,
        email_hint: str | None = None,
    ) -> str:
        """Resolve identity and upsert developer_profile. Returns dp_id."""
        async with self.pool.acquire() as conn:
            # Search by github_username first
            dp_id = None
            if github_username:
                row = await conn.fetchrow(
                    "SELECT id FROM developer_profile "
                    "WHERE github_username = $1 AND is_deleted = FALSE",
                    github_username,
                )
                if row:
                    dp_id = row["id"]

            # Search by hf_username
            if not dp_id and hf_username:
                row = await conn.fetchrow(
                    "SELECT id FROM developer_profile "
                    "WHERE huggingface_username = $1 AND is_deleted = FALSE",
                    hf_username,
                )
                if row:
                    dp_id = row["id"]

            if dp_id:
                # Update with any additional platform links
                await conn.execute(
                    "UPDATE developer_profile SET "
                    "github_username = COALESCE($2, github_username), "
                    "huggingface_username = COALESCE($3, huggingface_username), "
                    "email_hint = COALESCE($4, email_hint), "
                    "updated_at = NOW() "
                    "WHERE id = $1",
                    dp_id, github_username, hf_username, email_hint,
                )
                return dp_id

            # Create new
            dp_id = f"dp_{uuid.uuid4()}"
            await conn.execute(
                "INSERT INTO developer_profile "
                "(id, github_username, huggingface_username, email_hint, "
                "ingestion_status, created_at, updated_at) "
                "VALUES ($1, $2, $3, $4, 'pending', NOW(), NOW())",
                dp_id, github_username, hf_username, email_hint,
            )
            return dp_id

    # ---------- Build domain data from raw tables ----------

    async def build_gh_data(self, login: str) -> dict[str, Any]:
        """Build GH data dict from gh_users + gh_repositories."""
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT login, name, email, bio, company, location, "
                "website_url, avatar_url, followers, public_repos, "
                "social_accounts, contribution_stats "
                "FROM gh_users WHERE login = $1",
                login,
            )
            if not user:
                return {}

            data: dict[str, Any] = {
                "display_name": user["name"],
                "bio": user["bio"],
                "company": user["company"],
                "location": user["location"],
                "website": user["website_url"],
                "avatar_url": user["avatar_url"],
                "total_followers": user["followers"] or 0,
                "total_repos": user["public_repos"] or 0,
            }

            # Contribution stats
            cs = user["contribution_stats"]
            if cs and isinstance(cs, str):
                cs = json.loads(cs)
            if cs and isinstance(cs, dict):
                data["total_contributions"] = (
                    (cs.get("totalCommitContributions") or 0)
                    + (cs.get("totalPullRequestContributions") or 0)
                    + (cs.get("totalIssueContributions") or 0)
                )

            # Stars from repos
            stars = await conn.fetchval(
                "SELECT COALESCE(SUM(stars), 0) FROM gh_repositories WHERE owner_id = "
                "(SELECT id FROM gh_users WHERE login = $1)",
                login,
            )
            data["total_stars"] = stars or 0

            # Languages from repos
            lang_rows = await conn.fetch(
                "SELECT DISTINCT primary_language FROM gh_repositories "
                "WHERE owner_id = (SELECT id FROM gh_users WHERE login = $1) "
                "AND primary_language IS NOT NULL",
                login,
            )
            data["languages"] = [r["primary_language"] for r in lang_rows]

            # Topics from repos
            topic_rows = await conn.fetch(
                "SELECT DISTINCT unnest(topics) as topic FROM gh_repositories "
                "WHERE owner_id = (SELECT id FROM gh_users WHERE login = $1)",
                login,
            )
            data["topics"] = [r["topic"] for r in topic_rows]

            return data

    async def build_hf_data(self, username: str) -> dict[str, Any]:
        """Build HF data dict from hf_users + hf_models + hf_datasets."""
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT username, fullname, avatar_url, bio, "
                "num_models, num_datasets, num_followers "
                "FROM hf_users WHERE username = $1",
                username,
            )
            if not user:
                return {}

            data: dict[str, Any] = {
                "display_name": user["fullname"],
                "bio": user["bio"],
                "avatar_url": user["avatar_url"],
                "total_hf_models": user["num_models"] or 0,
                "total_hf_datasets": user["num_datasets"] or 0,
            }

            # Downloads and spaces
            dl = await conn.fetchval(
                "SELECT COALESCE(SUM(downloads_30d), 0) FROM hf_models WHERE author = $1",
                username,
            )
            data["total_hf_downloads"] = dl or 0

            # Spaces count (models with pipeline_tag that look like spaces)
            spaces = await conn.fetchval(
                "SELECT COUNT(*) FROM hf_models WHERE author = $1 AND pipeline_tag IS NOT NULL",
                username,
            )
            data["total_hf_spaces"] = spaces or 0

            return data

    async def build_ln_data(self, linkedin_url: str) -> dict[str, Any]:
        """Build LN data dict from ln_users."""
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT full_name, headline, summary, city, country, "
                "profile_pic_url, current_company, current_title, industry, "
                "num_connections, experiences, education, skills, certifications "
                "FROM ln_users WHERE linkedin_url = $1",
                linkedin_url,
            )
            if not user:
                return {}

            # Calculate years of experience from experiences JSONB
            experiences = user["experiences"] or []
            years = 0
            if isinstance(experiences, list):
                for exp in experiences:
                    starts = exp.get("starts_at") or {}
                    ends = exp.get("ends_at") or {}
                    start_year = starts.get("year")
                    end_year = ends.get("year") or datetime.now(timezone.utc).year
                    if start_year:
                        years += max(0, end_year - start_year)

            # Build job_history
            job_history = []
            if isinstance(experiences, list):
                for exp in experiences:
                    job_history.append({
                        "title": exp.get("title"),
                        "company": exp.get("company"),
                        "starts_at": exp.get("starts_at"),
                        "ends_at": exp.get("ends_at"),
                        "description": exp.get("description"),
                    })

            location_parts = [p for p in [user["city"], user["country"]] if p]

            return {
                "display_name": user["full_name"],
                "headline": user["headline"],
                "bio": user["summary"],
                "avatar_url": user["profile_pic_url"],
                "location": ", ".join(location_parts) if location_parts else None,
                "current_title": user["current_title"],
                "current_company": user["current_company"],
                "industry": user["industry"],
                "years_of_experience": years,
                "job_history": job_history,
                "education": user["education"] or [],
                "certifications": user["certifications"] or [],
                "connections": user["num_connections"],
                "skills": list(user["skills"]) if user["skills"] else [],
            }

    # ---------- Layer 2: Domain merge upserts ----------

    async def merge_developer_profile(
        self, dp_id: str, merged_data: dict[str, Any]
    ) -> str:
        """Upsert merged GH+HF data into developer_profile."""
        now = datetime.now(timezone.utc)
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE developer_profile SET "
                "display_name = $2, bio = $3, avatar_url = $4, "
                "company = $5, location = $6, website = $7, "
                "total_repos = $8, total_stars = $9, total_contributions = $10, "
                "total_followers = $11, total_hf_models = $12, total_hf_datasets = $13, "
                "total_hf_spaces = $14, total_hf_downloads = $15, total_papers = $16, "
                "languages = $17, skills = $18, topics = $19, "
                "dev_source_priority = $20, dev_merged_at = $21, "
                "ingestion_status = 'completed', last_ingested_at = $21, "
                "updated_at = $21 "
                "WHERE id = $1",
                dp_id,
                merged_data.get("display_name"),
                merged_data.get("bio"),
                merged_data.get("avatar_url"),
                merged_data.get("company"),
                merged_data.get("location"),
                merged_data.get("website"),
                merged_data.get("total_repos", 0),
                merged_data.get("total_stars", 0),
                merged_data.get("total_contributions", 0),
                merged_data.get("total_followers", 0),
                merged_data.get("total_hf_models", 0),
                merged_data.get("total_hf_datasets", 0),
                merged_data.get("total_hf_spaces", 0),
                merged_data.get("total_hf_downloads", 0),
                merged_data.get("total_papers", 0),
                json.dumps(merged_data.get("languages", [])),
                json.dumps(merged_data.get("skills", [])),
                json.dumps(merged_data.get("topics", [])),
                json.dumps(merged_data.get("dev_source_priority", {})),
                now,
            )
        return dp_id

    async def upsert_social_profile(
        self, dp_id: str, merged_data: dict[str, Any],
        linkedin_url: str | None = None, x_handle: str | None = None,
    ) -> str:
        """Upsert merged LN+X data into social_profile."""
        now = datetime.now(timezone.utc)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM social_profile WHERE developer_profile_id = $1",
                dp_id,
            )
            if row:
                sp_id = row["id"]
                await conn.execute(
                    "UPDATE social_profile SET "
                    "linkedin_url = COALESCE($2, linkedin_url), "
                    "x_handle = COALESCE($3, x_handle), "
                    "display_name = $4, headline = $5, bio = $6, "
                    "avatar_url = $7, location = $8, "
                    "current_title = $9, current_company = $10, "
                    "industry = $11, years_of_experience = $12, "
                    "job_history = $13, education = $14, "
                    "certifications = $15, connections = $16, "
                    "skills = $17, social_source_priority = $18, "
                    "social_merged_at = $19, updated_at = $19 "
                    "WHERE id = $1",
                    sp_id,
                    linkedin_url, x_handle,
                    merged_data.get("display_name"),
                    merged_data.get("headline"),
                    merged_data.get("bio"),
                    merged_data.get("avatar_url"),
                    merged_data.get("location"),
                    merged_data.get("current_title"),
                    merged_data.get("current_company"),
                    merged_data.get("industry"),
                    merged_data.get("years_of_experience"),
                    json.dumps(merged_data.get("job_history", [])),
                    json.dumps(merged_data.get("education", [])),
                    json.dumps(merged_data.get("certifications", [])),
                    merged_data.get("connections"),
                    json.dumps(merged_data.get("skills", [])),
                    json.dumps(merged_data.get("social_source_priority", {})),
                    now,
                )
            else:
                sp_id = f"sp_{uuid.uuid4()}"
                await conn.execute(
                    "INSERT INTO social_profile "
                    "(id, developer_profile_id, linkedin_url, x_handle, "
                    "display_name, headline, bio, avatar_url, location, "
                    "current_title, current_company, industry, "
                    "years_of_experience, job_history, education, "
                    "certifications, connections, skills, "
                    "social_source_priority, social_merged_at, "
                    "created_at, updated_at) "
                    "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$20,$20)",
                    sp_id, dp_id, linkedin_url, x_handle,
                    merged_data.get("display_name"),
                    merged_data.get("headline"),
                    merged_data.get("bio"),
                    merged_data.get("avatar_url"),
                    merged_data.get("location"),
                    merged_data.get("current_title"),
                    merged_data.get("current_company"),
                    merged_data.get("industry"),
                    merged_data.get("years_of_experience"),
                    json.dumps(merged_data.get("job_history", [])),
                    json.dumps(merged_data.get("education", [])),
                    json.dumps(merged_data.get("certifications", [])),
                    merged_data.get("connections"),
                    json.dumps(merged_data.get("skills", [])),
                    json.dumps(merged_data.get("social_source_priority", {})),
                    now,
                )
        return sp_id

    # ---------- Layer 3: Aggregated merge ----------

    async def upsert_aggregated_individual_profile(
        self, dp_id: str, merged_data: dict[str, Any]
    ) -> str:
        """Upsert aggregated profile from dev + social data."""
        now = datetime.now(timezone.utc)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM aggregated_individual_profile "
                "WHERE developer_profile_id = $1",
                dp_id,
            )
            if row:
                aip_id = row["id"]
                await conn.execute(
                    "UPDATE aggregated_individual_profile SET "
                    "display_name = $2, bio = $3, avatar_url = $4, "
                    "company = $5, location = $6, website = $7, "
                    "total_repos = $8, total_stars = $9, total_contributions = $10, "
                    "total_followers = $11, total_hf_models = $12, total_hf_datasets = $13, "
                    "total_hf_spaces = $14, total_hf_downloads = $15, total_papers = $16, "
                    "languages = $17, skills = $18, topics = $19, "
                    "headline = $20, current_title = $21, current_company = $22, "
                    "industry = $23, years_of_experience = $24, "
                    "job_history = $25, education = $26, certifications = $27, "
                    "connections = $28, source_priority = $29, "
                    "aggregated_at = $30, updated_at = $30 "
                    "WHERE id = $1",
                    aip_id,
                    merged_data.get("display_name"),
                    merged_data.get("bio"),
                    merged_data.get("avatar_url"),
                    merged_data.get("company"),
                    merged_data.get("location"),
                    merged_data.get("website"),
                    merged_data.get("total_repos", 0),
                    merged_data.get("total_stars", 0),
                    merged_data.get("total_contributions", 0),
                    merged_data.get("total_followers", 0),
                    merged_data.get("total_hf_models", 0),
                    merged_data.get("total_hf_datasets", 0),
                    merged_data.get("total_hf_spaces", 0),
                    merged_data.get("total_hf_downloads", 0),
                    merged_data.get("total_papers", 0),
                    json.dumps(merged_data.get("languages", [])),
                    json.dumps(merged_data.get("skills", [])),
                    json.dumps(merged_data.get("topics", [])),
                    merged_data.get("headline"),
                    merged_data.get("current_title"),
                    merged_data.get("current_company"),
                    merged_data.get("industry"),
                    merged_data.get("years_of_experience"),
                    json.dumps(merged_data.get("job_history", [])),
                    json.dumps(merged_data.get("education", [])),
                    json.dumps(merged_data.get("certifications", [])),
                    merged_data.get("connections"),
                    json.dumps(merged_data.get("source_priority", {})),
                    now,
                )
            else:
                aip_id = f"aip_{uuid.uuid4()}"
                await conn.execute(
                    "INSERT INTO aggregated_individual_profile "
                    "(id, developer_profile_id, display_name, bio, avatar_url, "
                    "company, location, website, "
                    "total_repos, total_stars, total_contributions, total_followers, "
                    "total_hf_models, total_hf_datasets, total_hf_spaces, "
                    "total_hf_downloads, total_papers, "
                    "languages, skills, topics, "
                    "headline, current_title, current_company, industry, "
                    "years_of_experience, job_history, education, certifications, "
                    "connections, source_priority, aggregated_at, "
                    "created_at, updated_at) "
                    "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,"
                    "$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30,$31,$31,$31)",
                    aip_id, dp_id,
                    merged_data.get("display_name"),
                    merged_data.get("bio"),
                    merged_data.get("avatar_url"),
                    merged_data.get("company"),
                    merged_data.get("location"),
                    merged_data.get("website"),
                    merged_data.get("total_repos", 0),
                    merged_data.get("total_stars", 0),
                    merged_data.get("total_contributions", 0),
                    merged_data.get("total_followers", 0),
                    merged_data.get("total_hf_models", 0),
                    merged_data.get("total_hf_datasets", 0),
                    merged_data.get("total_hf_spaces", 0),
                    merged_data.get("total_hf_downloads", 0),
                    merged_data.get("total_papers", 0),
                    json.dumps(merged_data.get("languages", [])),
                    json.dumps(merged_data.get("skills", [])),
                    json.dumps(merged_data.get("topics", [])),
                    merged_data.get("headline"),
                    merged_data.get("current_title"),
                    merged_data.get("current_company"),
                    merged_data.get("industry"),
                    merged_data.get("years_of_experience"),
                    json.dumps(merged_data.get("job_history", [])),
                    json.dumps(merged_data.get("education", [])),
                    json.dumps(merged_data.get("certifications", [])),
                    merged_data.get("connections"),
                    json.dumps(merged_data.get("source_priority", {})),
                    now,
                )
        return aip_id

    # ---------- Layer 4: Cohesive enrichment ----------

    async def upsert_cohesive_individual_profile(
        self, dp_id: str, merged_data: dict[str, Any],
        embedding_text: str | None = None,
    ) -> str:
        """Upsert cohesive profile from aggregated data + embedding."""
        now = datetime.now(timezone.utc)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM cohesive_individual_profile "
                "WHERE developer_profile_id = $1",
                dp_id,
            )
            if row:
                cip_id = row["id"]
                await conn.execute(
                    "UPDATE cohesive_individual_profile SET "
                    "display_name = $2, bio = $3, headline = $4, "
                    "location = $5, avatar_url = $6, company = $7, website = $8, "
                    "total_repos = $9, total_stars = $10, total_contributions = $11, "
                    "total_followers = $12, total_hf_models = $13, total_hf_datasets = $14, "
                    "total_hf_spaces = $15, total_hf_downloads = $16, total_papers = $17, "
                    "languages = $18, skills = $19, topics = $20, "
                    "years_of_experience = $21, current_title = $22, "
                    "current_company = $23, job_history = $24, "
                    "embedding_text = $25, source_priority = $26, "
                    "merged_at = $27 "
                    "WHERE id = $1",
                    cip_id,
                    merged_data.get("display_name"),
                    merged_data.get("bio"),
                    merged_data.get("headline"),
                    merged_data.get("location"),
                    merged_data.get("avatar_url"),
                    merged_data.get("company"),
                    merged_data.get("website"),
                    merged_data.get("total_repos", 0),
                    merged_data.get("total_stars", 0),
                    merged_data.get("total_contributions", 0),
                    merged_data.get("total_followers", 0),
                    merged_data.get("total_hf_models", 0),
                    merged_data.get("total_hf_datasets", 0),
                    merged_data.get("total_hf_spaces", 0),
                    merged_data.get("total_hf_downloads", 0),
                    merged_data.get("total_papers", 0),
                    json.dumps(merged_data.get("languages", [])),
                    json.dumps(merged_data.get("skills", [])),
                    json.dumps(merged_data.get("topics", [])),
                    merged_data.get("years_of_experience"),
                    merged_data.get("current_title"),
                    merged_data.get("current_company"),
                    json.dumps(merged_data.get("job_history", [])),
                    embedding_text,
                    json.dumps(merged_data.get("source_priority", {})),
                    now,
                )
            else:
                cip_id = f"cip_{uuid.uuid4()}"
                await conn.execute(
                    "INSERT INTO cohesive_individual_profile "
                    "(id, developer_profile_id, display_name, bio, headline, "
                    "location, avatar_url, company, website, "
                    "total_repos, total_stars, total_contributions, total_followers, "
                    "total_hf_models, total_hf_datasets, total_hf_spaces, "
                    "total_hf_downloads, total_papers, "
                    "languages, skills, topics, "
                    "years_of_experience, current_title, current_company, "
                    "job_history, embedding_text, source_priority, merged_at) "
                    "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,"
                    "$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28)",
                    cip_id, dp_id,
                    merged_data.get("display_name"),
                    merged_data.get("bio"),
                    merged_data.get("headline"),
                    merged_data.get("location"),
                    merged_data.get("avatar_url"),
                    merged_data.get("company"),
                    merged_data.get("website"),
                    merged_data.get("total_repos", 0),
                    merged_data.get("total_stars", 0),
                    merged_data.get("total_contributions", 0),
                    merged_data.get("total_followers", 0),
                    merged_data.get("total_hf_models", 0),
                    merged_data.get("total_hf_datasets", 0),
                    merged_data.get("total_hf_spaces", 0),
                    merged_data.get("total_hf_downloads", 0),
                    merged_data.get("total_papers", 0),
                    json.dumps(merged_data.get("languages", [])),
                    json.dumps(merged_data.get("skills", [])),
                    json.dumps(merged_data.get("topics", [])),
                    merged_data.get("years_of_experience"),
                    merged_data.get("current_title"),
                    merged_data.get("current_company"),
                    json.dumps(merged_data.get("job_history", [])),
                    embedding_text,
                    json.dumps(merged_data.get("source_priority", {})),
                    now,
                )
        return cip_id

    # ---------- Merge audit ----------

    async def write_merge_audit(
        self,
        dp_id: str,
        merge_level: str,
        target_table: str,
        merge_run_id: str,
        field_decisions: list[dict[str, Any]],
    ) -> None:
        """Write merge audit log entries for one merge operation."""
        rows = []
        now = datetime.now(timezone.utc)
        for fd in field_decisions:
            if fd.get("action") == "unchanged":
                continue
            rows.append((
                f"mal_{uuid.uuid4()}",
                dp_id,
                merge_level,
                target_table,
                merge_run_id,
                fd["field"],
                fd["winner"],
                fd.get("value"),
                fd.get("previous"),
                json.dumps(fd["overridden"]) if fd.get("overridden") else None,
                fd["action"],
                now,
            ))
        if not rows:
            return
        async with self.pool.acquire() as conn:
            await conn.executemany(
                "INSERT INTO merge_audit_log "
                "(id, developer_profile_id, merge_level, target_table, "
                "merge_run_id, field_name, winning_source, winning_value, "
                "previous_value, overridden_values, action, merged_at) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)",
                rows,
            )

    # ---------- LinkedIn URL extraction ----------

    async def extract_linkedin_urls(self) -> list[dict[str, Any]]:
        """Extract LinkedIn URLs from GH/HF data for discovery."""
        results: list[dict[str, Any]] = []
        async with self.pool.acquire() as conn:
            # Source 1: gh_users.social_accounts JSONB
            gh_rows = await conn.fetch(
                "SELECT login, social_accounts FROM gh_users "
                "WHERE social_accounts IS NOT NULL"
            )
            for r in gh_rows:
                accounts = r["social_accounts"]
                if isinstance(accounts, str):
                    accounts = json.loads(accounts)
                if isinstance(accounts, list):
                    for acc in accounts:
                        provider = (acc.get("provider") or "").upper()
                        url = acc.get("url", "")
                        if provider == "LINKEDIN" and url:
                            results.append({
                                "linkedin_url": _normalize_linkedin_url(url),
                                "source_platform": "github",
                                "source_username": r["login"],
                                "priority": 1,
                            })

            # Source 2: gh_users.bio / website_url regex
            bio_rows = await conn.fetch(
                "SELECT login, bio, website_url FROM gh_users "
                "WHERE bio LIKE '%linkedin.com/in/%' "
                "   OR website_url LIKE '%linkedin.com/in/%'"
            )
            import re
            ln_pattern = re.compile(r"linkedin\.com/in/([a-zA-Z0-9_-]+)")
            for r in bio_rows:
                for field in ["bio", "website_url"]:
                    text = r[field] or ""
                    match = ln_pattern.search(text)
                    if match:
                        handle = match.group(1)
                        url = f"https://www.linkedin.com/in/{handle}"
                        results.append({
                            "linkedin_url": url,
                            "source_platform": "github",
                            "source_username": r["login"],
                            "priority": 3 if field == "bio" else 2,
                        })

            # Source 3: hf_users.linkedin
            hf_rows = await conn.fetch(
                "SELECT username, linkedin FROM hf_users "
                "WHERE linkedin IS NOT NULL AND linkedin != ''"
            )
            for r in hf_rows:
                url = r["linkedin"]
                if "linkedin.com" in (url or ""):
                    results.append({
                        "linkedin_url": _normalize_linkedin_url(url),
                        "source_platform": "huggingface",
                        "source_username": r["username"],
                        "priority": 1,
                    })

        # Deduplicate by URL (keep highest priority)
        seen: dict[str, dict[str, Any]] = {}
        for item in results:
            url = item["linkedin_url"]
            if url not in seen or item["priority"] < seen[url]["priority"]:
                seen[url] = item
        return list(seen.values())


def _normalize_linkedin_url(url: str) -> str:
    """Normalize LinkedIn URL to https://www.linkedin.com/in/<handle>."""
    import re

    match = re.search(r"linkedin\.com/in/([a-zA-Z0-9_-]+)", url)
    if match:
        return f"https://www.linkedin.com/in/{match.group(1)}"
    return url
