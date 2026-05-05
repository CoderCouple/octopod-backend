"""
Postgres storage: idempotent upserts using ON CONFLICT.
Uses asyncpg connection pool for high concurrency.
"""
from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import asyncpg

from app.ingest.common.metrics import db_operation_seconds, db_operations

log = logging.getLogger(__name__)


@asynccontextmanager
async def _timed(operation: str) -> AsyncIterator[None]:
    start = time.monotonic()
    try:
        yield
        db_operations.labels(operation=operation, status="ok").inc()
    except Exception:
        db_operations.labels(operation=operation, status="error").inc()
        raise
    finally:
        db_operation_seconds.labels(operation=operation).observe(time.monotonic() - start)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class GHStorage:
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
            raise RuntimeError("GHStorage not connected; call connect() first")
        return self._pool

    async def init_schema(self, sql: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(sql)

    # ---------- Extraction helpers ----------

    @staticmethod
    def _extract_social_accounts(user: dict[str, Any]) -> str | None:
        nodes = (user.get("socialAccounts") or {}).get("nodes")
        if not nodes:
            return None
        return json.dumps(nodes)

    @staticmethod
    def _extract_contribution_stats(user: dict[str, Any]) -> str | None:
        cc = user.get("contributionsCollection")
        if not cc:
            return None
        return json.dumps({
            "totalCommitContributions": cc.get("totalCommitContributions", 0),
            "totalPullRequestContributions": cc.get("totalPullRequestContributions", 0),
            "totalIssueContributions": cc.get("totalIssueContributions", 0),
            "totalRepositoryContributions": cc.get("totalRepositoryContributions", 0),
        })

    @staticmethod
    def _extract_contribution_calendar(user: dict[str, Any]) -> str | None:
        cc = user.get("contributionsCollection")
        if not cc:
            return None
        calendar = cc.get("contributionCalendar")
        if not calendar:
            return None
        return json.dumps(calendar)

    # ---------- Upserts ----------

    async def upsert_user(self, user: dict[str, Any]) -> int:
        """Insert or update a user row. Returns the user's DB id."""
        row_id = user["databaseId"]
        async with _timed("upsert_user"):
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO gh_users (
                        id, login, name, email, bio, company, location,
                        website_url, twitter, avatar_url, followers, following,
                        public_repos, is_hireable, created_at, updated_at_gh,
                        social_accounts, contribution_stats, contribution_calendar, raw
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20)
                    ON CONFLICT (id) DO UPDATE SET
                        login = EXCLUDED.login,
                        name = EXCLUDED.name,
                        email = EXCLUDED.email,
                        bio = EXCLUDED.bio,
                        company = EXCLUDED.company,
                        location = EXCLUDED.location,
                        website_url = EXCLUDED.website_url,
                        twitter = EXCLUDED.twitter,
                        avatar_url = EXCLUDED.avatar_url,
                        followers = EXCLUDED.followers,
                        following = EXCLUDED.following,
                        public_repos = EXCLUDED.public_repos,
                        is_hireable = EXCLUDED.is_hireable,
                        updated_at_gh = EXCLUDED.updated_at_gh,
                        social_accounts = EXCLUDED.social_accounts,
                        contribution_stats = EXCLUDED.contribution_stats,
                        contribution_calendar = EXCLUDED.contribution_calendar,
                        ingested_at = NOW(),
                        raw = EXCLUDED.raw
                    """,
                    row_id,
                    user["login"],
                    user.get("name"),
                    user.get("email"),
                    user.get("bio"),
                    user.get("company"),
                    user.get("location"),
                    user.get("websiteUrl"),
                    user.get("twitterUsername"),
                    user.get("avatarUrl"),
                    (user.get("followers") or {}).get("totalCount", 0),
                    (user.get("following") or {}).get("totalCount", 0),
                    len((user.get("repositories") or {}).get("nodes") or []),
                    user.get("isHireable"),
                    _parse_ts(user.get("createdAt")),
                    _parse_ts(user.get("updatedAt")),
                    self._extract_social_accounts(user),
                    self._extract_contribution_stats(user),
                    self._extract_contribution_calendar(user),
                    json.dumps(user),
                )
        return row_id

    async def upsert_repos(
        self, owner_id: int, repos: Iterable[dict[str, Any]]
    ) -> list[int]:
        """Batch-upsert repositories for a user. Returns list of repo ids."""
        rows: list[tuple] = []
        repo_ids: list[int] = []
        for r in repos:
            if not r or not r.get("databaseId"):
                continue
            topics = [
                n["topic"]["name"]
                for n in (r.get("repositoryTopics") or {}).get("nodes", [])
                if n.get("topic")
            ]
            rows.append((
                r["databaseId"],
                owner_id,
                r["name"],
                r["nameWithOwner"],
                r.get("description"),
                (r.get("primaryLanguage") or {}).get("name"),
                bool(r.get("isFork")),
                bool(r.get("isArchived")),
                r.get("stargazerCount", 0),
                r.get("forkCount", 0),
                (r.get("watchers") or {}).get("totalCount", 0),
                (r.get("issues") or {}).get("totalCount", 0),
                r.get("diskUsage", 0) or 0,
                _parse_ts(r.get("createdAt")),
                _parse_ts(r.get("updatedAt")),
                _parse_ts(r.get("pushedAt")),
                topics,
                json.dumps(r),
            ))
            repo_ids.append(r["databaseId"])

        if not rows:
            return []

        async with _timed("upsert_repos"):
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.executemany(
                        """
                        INSERT INTO gh_repositories (
                            id, owner_id, name, full_name, description, primary_language,
                            is_fork, is_archived, stars, forks, watchers, open_issues,
                            size_kb, created_at, updated_at_gh, pushed_at, topics, raw
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)
                        ON CONFLICT (id) DO UPDATE SET
                            description = EXCLUDED.description,
                            primary_language = EXCLUDED.primary_language,
                            is_archived = EXCLUDED.is_archived,
                            stars = EXCLUDED.stars,
                            forks = EXCLUDED.forks,
                            watchers = EXCLUDED.watchers,
                            open_issues = EXCLUDED.open_issues,
                            size_kb = EXCLUDED.size_kb,
                            updated_at_gh = EXCLUDED.updated_at_gh,
                            pushed_at = EXCLUDED.pushed_at,
                            topics = EXCLUDED.topics,
                            ingested_at = NOW(),
                            raw = EXCLUDED.raw
                        """,
                        rows,
                    )
        return repo_ids

    async def upsert_commits(
        self, repo_id: int, commits: Iterable[dict[str, Any]]
    ) -> int:
        rows = []
        for c in commits:
            if not c or not c.get("oid"):
                continue
            author = c.get("author") or {}
            author_user = author.get("user") or {}
            rows.append((
                c["oid"],
                repo_id,
                author_user.get("databaseId"),
                author_user.get("login"),
                author.get("email"),
                c.get("message"),
                _parse_ts(c.get("committedDate")),
                c.get("additions"),
                c.get("deletions"),
                c.get("changedFilesIfAvailable"),
            ))
        if not rows:
            return 0
        async with self.pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO gh_commits (
                    oid, repo_id, author_id, author_login, author_email,
                    message, committed_at, additions, deletions, changed_files
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                ON CONFLICT (oid, repo_id) DO NOTHING
                """,
                rows,
            )
        return len(rows)

    async def upsert_events(
        self, user_id: int, events: Iterable[dict[str, Any]]
    ) -> int:
        rows = []
        for e in events:
            if not e or not e.get("id"):
                continue
            rows.append((
                str(e["id"]),
                user_id,
                e.get("type", "Unknown"),
                (e.get("repo") or {}).get("name"),
                json.dumps(e.get("payload") or {}),
                _parse_ts(e.get("created_at")),
            ))
        if not rows:
            return 0
        async with self.pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO gh_activity_events (id, user_id, type, repo_name, payload, created_at)
                VALUES ($1,$2,$3,$4,$5,$6)
                ON CONFLICT (id) DO NOTHING
                """,
                rows,
            )
        return len(rows)

    # ---------- Checkpoints ----------

    async def mark_checkpoint(
        self, login: str, status: str, error: str | None = None, job_id: str | None = None
    ) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO gh_checkpoints (login, status, last_attempt, last_success, last_error, attempt_count, last_job_id)
                VALUES ($1, $2, NOW(),
                        CASE WHEN $2 = 'ingested' THEN NOW() ELSE NULL END,
                        $3, 1, $4)
                ON CONFLICT (login) DO UPDATE SET
                    status = EXCLUDED.status,
                    last_attempt = NOW(),
                    last_success = CASE WHEN EXCLUDED.status = 'ingested'
                                        THEN NOW() ELSE gh_checkpoints.last_success END,
                    last_error = EXCLUDED.last_error,
                    attempt_count = gh_checkpoints.attempt_count + 1,
                    last_job_id = COALESCE(EXCLUDED.last_job_id, gh_checkpoints.last_job_id)
                """,
                login, status, error, job_id,
            )

    async def recently_ingested(self, login: str, within_hours: int) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 1 FROM gh_checkpoints
                WHERE login = $1 AND status = 'ingested'
                  AND last_success > NOW() - make_interval(hours => $2)
                """,
                login, within_hours,
            )
        return row is not None

    async def bulk_mark_discovered(
        self,
        logins: list[str],
        source: str,
        org_source: str | None = None,
        job_id: str | None = None,
    ) -> int:
        """Batch-insert discovered users. Skips any login that already exists."""
        if not logins:
            return 0
        rows = [(login, source, org_source, job_id) for login in logins]
        async with _timed("bulk_mark_discovered"):
            async with self.pool.acquire() as conn:
                await conn.executemany(
                    """
                    INSERT INTO gh_checkpoints (login, status, discovered_at, source, org_source, last_job_id)
                    VALUES ($1, 'discovered', NOW(), $2, $3, $4)
                    ON CONFLICT (login) DO NOTHING
                    """,
                    rows,
                )
        return len(logins)

    async def mark_org_fetched(
        self, org_login: str, member_count: int, job_id: str | None = None
    ) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO gh_org_checkpoints (org_login, status, member_count, discovered_at, last_fetched_at, last_job_id)
                VALUES ($1, 'fetched', $2, NOW(), NOW(), $3)
                ON CONFLICT (org_login) DO UPDATE SET
                    status = 'fetched',
                    member_count = EXCLUDED.member_count,
                    last_fetched_at = NOW(),
                    last_job_id = EXCLUDED.last_job_id
                """,
                org_login, member_count, job_id,
            )

    async def is_org_fetched(self, org_login: str, within_hours: int) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 1 FROM gh_org_checkpoints
                WHERE org_login = $1 AND status = 'fetched'
                  AND last_fetched_at > NOW() - make_interval(hours => $2)
                """,
                org_login, within_hours,
            )
        return row is not None
