"""
Discover top Hugging Face users/orgs by weighted downloads + likes.

Strategy: list top models sorted by downloads, aggregate metrics by author,
then do a second pass sorted by likes. Unlike GitHub, HF has no per-query
result cap, just standard pagination, so this is straightforward.

Final score uses rank normalization to fairly combine two metrics with very
different magnitudes (downloads can be billions, likes in the thousands).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.ingest.common.errors import PermanentError, TransientError

from .client import HFClient, _parse_next_link
from .config import HFConfig

log = logging.getLogger(__name__)


@dataclass
class AuthorCandidate:
    username: str
    total_downloads: int = 0
    total_likes: int = 0
    num_models: int = 0
    downloads_rank: int = 0
    likes_rank: int = 0
    score: float = 0.0


async def _list_top_models(
    client: HFClient,
    sort: str,
    max_models: int,
    *,
    pipeline_tag: str | None = None,
    library: str | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    params: dict[str, Any] = {"sort": sort, "direction": "-1", "limit": 100}
    if pipeline_tag:
        params["pipeline_tag"] = pipeline_tag
    if library:
        params["library"] = library
    path = "/api/models"
    next_url: str | None = None
    first = True
    while len(out) < max_models:
        try:
            if next_url:
                resp = await client._request("GET", next_url)
            else:
                resp = await client._request(
                    "GET", path, params=params if first else None
                )
                first = False
        except (PermanentError, TransientError) as e:
            log.warning(
                "HF list_top_models(sort=%s) failed at %d: %s", sort, len(out), e
            )
            break

        page = resp.json()
        if not isinstance(page, list) or not page:
            break
        out.extend(page)
        if len(page) < 100:
            break

        link = resp.headers.get("Link")
        next_url = _parse_next_link(link)
        if not next_url:
            break

    return out[:max_models]


def _author_of(model_id: str) -> str | None:
    if "/" not in model_id:
        return None
    return model_id.split("/", 1)[0]


def _aggregate_by_author(
    models: list[dict[str, Any]],
) -> dict[str, AuthorCandidate]:
    authors: dict[str, AuthorCandidate] = {}
    for m in models:
        mid = m.get("id")
        author = _author_of(mid) if mid else None
        if not author:
            continue
        cand = authors.setdefault(author, AuthorCandidate(username=author))
        cand.total_downloads += int(m.get("downloads") or 0)
        cand.total_likes += int(m.get("likes") or 0)
        cand.num_models += 1
    return authors


def _rank_and_score(
    authors: dict[str, AuthorCandidate], alpha: float
) -> list[AuthorCandidate]:
    """alpha weights downloads; (1-alpha) weights likes."""
    items = list(authors.values())
    for idx, a in enumerate(
        sorted(items, key=lambda x: x.total_downloads, reverse=True)
    ):
        a.downloads_rank = idx
    for idx, a in enumerate(
        sorted(items, key=lambda x: x.total_likes, reverse=True)
    ):
        a.likes_rank = idx

    n = max(1, len(items))
    for a in items:
        d_norm = 1.0 - (a.downloads_rank / n)
        l_norm = 1.0 - (a.likes_rank / n)
        a.score = alpha * d_norm + (1.0 - alpha) * l_norm

    items.sort(key=lambda x: x.score, reverse=True)
    return items


async def discover_top_authors(
    config: HFConfig,
    n: int = 5000,
    alpha: float = 0.5,
    *,
    download_pool_size: int = 20000,
    likes_pool_size: int = 10000,
    pipeline_tag: str | None = None,
    library: str | None = None,
) -> list[AuthorCandidate]:
    """Return top-N authors by weighted downloads + likes score."""
    async with HFClient(config) as client:
        log.info("Phase 1/2: fetching top %d models by downloads", download_pool_size)
        by_downloads = await _list_top_models(
            client, "downloads", download_pool_size,
            pipeline_tag=pipeline_tag, library=library,
        )
        log.info("  got %d models", len(by_downloads))

        log.info("Phase 2/2: fetching top %d models by likes", likes_pool_size)
        by_likes = await _list_top_models(
            client, "likes", likes_pool_size,
            pipeline_tag=pipeline_tag, library=library,
        )
        log.info("  got %d models", len(by_likes))

    by_id: dict[str, dict[str, Any]] = {}
    for m in by_downloads + by_likes:
        if m.get("id"):
            by_id[m["id"]] = m
    log.info("merged to %d unique models", len(by_id))

    authors = _aggregate_by_author(list(by_id.values()))
    ranked = _rank_and_score(authors, alpha)
    log.info(
        "Aggregated to %d unique authors; returning top %d", len(ranked), n
    )
    return ranked[:n]
