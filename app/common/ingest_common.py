"""Shared helpers for ingest API controllers."""
from __future__ import annotations

from typing import Any

import asyncpg


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Convert asyncpg Record dicts to JSON-safe values."""
    out: dict[str, Any] = {}
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


async def _fetch_gh_user_data(conn: asyncpg.Connection, login: str) -> dict[str, Any]:
    """Fetch a GitHub user profile with repos, commits, and events."""
    user = await conn.fetchrow(
        "SELECT id, login, name, email, bio, company, location, "
        "website_url, twitter, avatar_url, followers, following, "
        "public_repos, is_hireable, created_at, updated_at_gh, "
        "social_accounts, contribution_stats, contribution_calendar, "
        "ingested_at "
        "FROM gh_users WHERE login = $1",
        login,
    )
    if not user:
        return {"login": login, "found": False}

    user_dict = _serialize_row(dict(user))
    user_dict.pop("raw", None)

    repos = await conn.fetch(
        "SELECT id, name, full_name, description, primary_language, is_fork, "
        "is_archived, stars, forks, watchers, open_issues, size_kb, "
        "created_at, updated_at_gh, pushed_at, topics, ingested_at "
        "FROM gh_repositories WHERE owner_id = $1 ORDER BY stars DESC",
        user["id"],
    )
    user_dict["repositories"] = [_serialize_row(dict(r)) for r in repos]

    commit_count = await conn.fetchval(
        "SELECT COUNT(*) FROM gh_commits WHERE author_id = $1", user["id"]
    )
    user_dict["total_commits"] = commit_count

    event_count = await conn.fetchval(
        "SELECT COUNT(*) FROM gh_activity_events WHERE user_id = $1", user["id"]
    )
    user_dict["total_events"] = event_count

    return user_dict


async def _fetch_hf_user_data(conn: asyncpg.Connection, username: str) -> dict[str, Any]:
    """Fetch a HuggingFace user profile with models and datasets."""
    user = await conn.fetchrow(
        "SELECT username, type, fullname, avatar_url, is_pro, "
        "num_models, num_datasets, num_followers, num_following, num_likes, "
        "bio, website_url, twitter, github_username, linkedin, "
        "created_at, ingested_at "
        "FROM hf_users WHERE username = $1",
        username,
    )
    if not user:
        return {"login": username, "found": False}

    user_dict = _serialize_row(dict(user))
    user_dict.pop("raw", None)

    models = await conn.fetch(
        "SELECT id, name, pipeline_tag, library_name, license, base_model, "
        "downloads_30d, downloads_all, likes, is_private, is_gated, "
        "tags, languages, created_at, last_modified, ingested_at "
        "FROM hf_models WHERE author = $1 ORDER BY downloads_30d DESC",
        username,
    )
    user_dict["models"] = [_serialize_row(dict(m)) for m in models]

    datasets = await conn.fetch(
        "SELECT id, name, task_categories, license, size_category, "
        "downloads_30d, likes, is_private, is_gated, "
        "tags, languages, created_at, last_modified, ingested_at "
        "FROM hf_datasets WHERE author = $1 ORDER BY downloads_30d DESC",
        username,
    )
    user_dict["datasets"] = [_serialize_row(dict(d)) for d in datasets]

    return user_dict
