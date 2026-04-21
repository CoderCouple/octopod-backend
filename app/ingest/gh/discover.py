"""
Discover top GitHub users by weighted followers + stars score.

The hard part: GitHub's search API caps results at 1,000 per query. To get 5k+
unique top users, we stratify queries by follower-count bands and union.
For the "stars" component we do a separate pass over top repositories and
aggregate their owners' star counts.

Final score = alpha * followers_rank + (1 - alpha) * stars_rank (rank-based
so the two very different magnitudes combine fairly).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from app.ingest.common.errors import PermanentError, TransientError

from .client import GitHubClient
from .config import GHConfig

log = logging.getLogger(__name__)


DEFAULT_FOLLOWER_BANDS: list[tuple[int, int | None]] = [
    (50000, None),
    (20000, 50000),
    (10000, 20000),
    (5000, 10000),
    (3000, 5000),
    (2000, 3000),
    (1500, 2000),
    (1200, 1500),
    (1000, 1200),
    (800, 1000),
    (600, 800),
    (500, 600),
]


@dataclass
class UserCandidate:
    login: str
    followers: int = 0
    total_stars: int = 0
    followers_rank: int = 0
    stars_rank: int = 0
    score: float = 0.0


async def _search_users_page(
    client: GitHubClient, query: str, page: int, per_page: int = 100
) -> dict[str, Any]:
    resp = await client._request(
        "GET",
        f"{client.config.rest_endpoint}/search/users",
        params={
            "q": query,
            "sort": "followers",
            "order": "desc",
            "per_page": per_page,
            "page": page,
        },
    )
    return resp.json()


async def _search_repos_page(
    client: GitHubClient, query: str, page: int, per_page: int = 100
) -> dict[str, Any]:
    resp = await client._request(
        "GET",
        f"{client.config.rest_endpoint}/search/repositories",
        params={
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": per_page,
            "page": page,
        },
    )
    return resp.json()


async def _collect_users_from_band(
    client: GitHubClient,
    lo: int,
    hi: int | None,
    max_per_band: int = 1000,
) -> dict[str, UserCandidate]:
    q = f"followers:>{lo}" if hi is None else f"followers:{lo}..{hi}"
    found: dict[str, UserCandidate] = {}
    page = 1
    per_page = 100
    while len(found) < max_per_band:
        try:
            data = await _search_users_page(client, q, page, per_page)
        except (PermanentError, TransientError) as e:
            log.warning("search failed q=%r page=%d: %s", q, page, e)
            break

        items = data.get("items") or []
        total = data.get("total_count", 0)
        for item in items:
            login = item.get("login")
            if not login:
                continue
            found.setdefault(login, UserCandidate(login=login))
        if len(items) < per_page:
            break
        page += 1
        if page > 10:
            if total > 1000:
                log.warning(
                    "band q=%r has %d results but GitHub caps at 1000; "
                    "narrow bands to capture tail",
                    q,
                    total,
                )
            break
    return found


async def _enrich_follower_counts(
    client: GitHubClient,
    candidates: dict[str, UserCandidate],
    concurrency: int,
) -> None:
    sem = asyncio.Semaphore(concurrency)

    async def one(login: str) -> None:
        async with sem:
            try:
                resp = await client._request(
                    "GET", f"{client.config.rest_endpoint}/users/{login}"
                )
                data = resp.json()
                candidates[login].followers = data.get("followers", 0)
            except (PermanentError, TransientError) as e:
                log.debug("enrich failed for %s: %s", login, e)

    await asyncio.gather(*(one(login) for login in list(candidates)))


async def _collect_top_repo_owners(
    client: GitHubClient, n_repos: int = 5000
) -> dict[str, int]:
    owners: dict[str, int] = {}
    star_bands: list[tuple[int, int | None]] = [
        (100000, None),
        (50000, 100000),
        (20000, 50000),
        (10000, 20000),
        (5000, 10000),
        (2000, 5000),
        (1000, 2000),
        (500, 1000),
    ]
    collected = 0
    for lo, hi in star_bands:
        if collected >= n_repos:
            break
        q = f"stars:>{lo}" if hi is None else f"stars:{lo}..{hi}"
        page = 1
        while collected < n_repos:
            try:
                data = await _search_repos_page(client, q, page, 100)
            except (PermanentError, TransientError) as e:
                log.warning("repo search failed q=%r: %s", q, e)
                break
            items = data.get("items") or []
            if not items:
                break
            for repo in items:
                owner = (repo.get("owner") or {}).get("login")
                stars = repo.get("stargazers_count", 0)
                if owner:
                    owners[owner] = owners.get(owner, 0) + stars
                    collected += 1
                    if collected >= n_repos:
                        break
            if len(items) < 100:
                break
            page += 1
            if page > 10:
                break
    return owners


def _rank_and_score(
    users: dict[str, UserCandidate], alpha: float
) -> list[UserCandidate]:
    """Assign ranks on both axes and compute a weighted rank-based score."""
    items = list(users.values())

    for idx, u in enumerate(
        sorted(items, key=lambda x: x.followers, reverse=True)
    ):
        u.followers_rank = idx
    for idx, u in enumerate(
        sorted(items, key=lambda x: x.total_stars, reverse=True)
    ):
        u.stars_rank = idx

    n = max(1, len(items))
    for u in items:
        f_norm = 1.0 - (u.followers_rank / n)
        s_norm = 1.0 - (u.stars_rank / n)
        u.score = alpha * f_norm + (1.0 - alpha) * s_norm

    items.sort(key=lambda x: x.score, reverse=True)
    return items


async def discover_top_users(
    config: GHConfig,
    n: int = 5000,
    alpha: float = 0.5,
    *,
    follower_bands: list[tuple[int, int | None]] | None = None,
    repo_pool_size: int = 5000,
    enrich_concurrency: int = 16,
) -> list[UserCandidate]:
    """Return the top-N users ranked by weighted followers+stars score."""
    from .token_pool import TokenPool

    pool = TokenPool(config.github_tokens)

    async with GitHubClient(config, pool) as client:
        log.info("Phase 1/3: discovering users by follower bands")
        all_users: dict[str, UserCandidate] = {}
        bands = follower_bands or DEFAULT_FOLLOWER_BANDS
        for lo, hi in bands:
            band_users = await _collect_users_from_band(client, lo, hi)
            log.info(
                "  band followers %s-%s: +%d users (total unique: %d)",
                lo,
                hi or "inf",
                len(band_users),
                len(set(all_users) | set(band_users)),
            )
            all_users.update(band_users)

        log.info("Phase 2/3: enriching with exact follower counts")
        await _enrich_follower_counts(client, all_users, enrich_concurrency)

        log.info("Phase 3/3: collecting top repo owners for star component")
        owner_stars = await _collect_top_repo_owners(client, repo_pool_size)
        for owner, stars in owner_stars.items():
            if owner not in all_users:
                all_users[owner] = UserCandidate(login=owner)
            all_users[owner].total_stars = stars

        ranked = _rank_and_score(all_users, alpha)
        log.info(
            "Discovered %d unique candidates; returning top %d", len(ranked), n
        )
        return ranked[:n]
