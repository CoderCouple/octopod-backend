"""Bridge orchestrator: runs the 4-layer merge pipeline."""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from app.ingest.bridge.config import BridgeConfig
from app.ingest.bridge.indexer import DualIndexer
from app.ingest.bridge.merge import (
    build_embedding_text,
    merge_aggregated_fields,
    merge_cohesive_fields,
    merge_dev_fields,
    merge_social_fields,
)
from app.ingest.bridge.storage import BridgeStorage
from app.ingest.common.job_tracker import JobTracker

log = logging.getLogger(__name__)


@dataclass
class SyncStats:
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0


class BridgeOrchestrator:
    def __init__(
        self,
        config: BridgeConfig,
        storage: BridgeStorage,
        job_tracker: JobTracker | None = None,
        indexer: DualIndexer | None = None,
    ) -> None:
        self._config = config
        self._storage = storage
        self._tracker = job_tracker
        self._indexer = indexer

    async def run(
        self,
        mode: str = "full",
        since_hours: int | None = None,
    ) -> SyncStats:
        """Run the bridge sync pipeline.

        Args:
            mode: "full" | "recent" | "gh_only" | "hf_only" | "ln_only"
            since_hours: Override config since_hours.
        """
        hours = since_hours or self._config.since_hours
        stats = SyncStats()
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        # Discover users to sync
        if mode in ("full", "recent", "gh_only"):
            await self._enqueue_gh_users(queue, hours)
        if mode in ("full", "recent", "hf_only"):
            await self._enqueue_hf_users(queue, hours)
        if mode in ("full", "recent", "ln_only"):
            await self._enqueue_ln_users(queue, hours)

        # Sentinel values for workers
        for _ in range(self._config.concurrency):
            await queue.put(None)

        # Run workers
        workers = [
            asyncio.create_task(self._worker(queue, stats))
            for _ in range(self._config.concurrency)
        ]
        await asyncio.gather(*workers)
        return stats

    async def _enqueue_gh_users(
        self, queue: asyncio.Queue, hours: int
    ) -> None:
        offset = 0
        while True:
            users = await self._storage.list_gh_users_to_sync(
                hours, self._config.batch_size, offset
            )
            if not users:
                break
            for u in users:
                await queue.put({
                    "type": "gh",
                    "login": u["login"],
                    "hf_username": None,
                    "linkedin_url": None,
                })
            offset += len(users)
            if len(users) < self._config.batch_size:
                break

    async def _enqueue_hf_users(
        self, queue: asyncio.Queue, hours: int
    ) -> None:
        offset = 0
        while True:
            users = await self._storage.list_hf_users_to_sync(
                hours, self._config.batch_size, offset
            )
            if not users:
                break
            for u in users:
                await queue.put({
                    "type": "hf",
                    "login": u.get("github_username"),
                    "hf_username": u["username"],
                    "linkedin_url": None,
                })
            offset += len(users)
            if len(users) < self._config.batch_size:
                break

    async def _enqueue_ln_users(
        self, queue: asyncio.Queue, hours: int
    ) -> None:
        offset = 0
        while True:
            users = await self._storage.list_ln_users_to_sync(
                hours, self._config.batch_size, offset
            )
            if not users:
                break
            for u in users:
                await queue.put({
                    "type": "ln",
                    "login": None,
                    "hf_username": None,
                    "linkedin_url": u["linkedin_url"],
                })
            offset += len(users)
            if len(users) < self._config.batch_size:
                break

    async def _worker(
        self, queue: asyncio.Queue, stats: SyncStats
    ) -> None:
        while True:
            item = await queue.get()
            if item is None:
                break
            identifier = (
                item.get("login")
                or item.get("hf_username")
                or item.get("linkedin_url")
                or "unknown"
            )
            try:
                if self._tracker:
                    await self._tracker.item_started(identifier)

                await self._sync_one(item)
                stats.processed += 1
                stats.succeeded += 1

                if self._tracker:
                    await self._tracker.item_completed(identifier)
            except Exception as e:
                stats.processed += 1
                stats.failed += 1
                log.exception("Failed to sync %s", identifier)
                if self._tracker:
                    await self._tracker.item_failed(
                        identifier, type(e).__name__, str(e)[:500]
                    )

    async def _sync_one(self, item: dict[str, Any]) -> None:
        """Full 4-layer sync for one user."""
        merge_run_id = f"mr_{uuid.uuid4()}"

        gh_login = item.get("login")
        hf_username = item.get("hf_username")
        linkedin_url = item.get("linkedin_url")

        # Step 1: Identity resolution
        dp_id = await self._storage.upsert_developer_profile(
            github_username=gh_login,
            hf_username=hf_username,
        )

        # Step 2: Build raw data from each platform
        gh_data = await self._storage.build_gh_data(gh_login) if gh_login else {}
        hf_data = await self._storage.build_hf_data(hf_username) if hf_username else {}
        ln_data = await self._storage.build_ln_data(linkedin_url) if linkedin_url else {}

        # Step 3: Layer 2 - Domain merge: developer_profile (GH+HF)
        dev_merged, dev_decisions = merge_dev_fields(gh_data, hf_data)
        await self._storage.merge_developer_profile(dp_id, dev_merged)
        await self._storage.write_merge_audit(
            dp_id, "domain_dev", "developer_profile", merge_run_id, dev_decisions
        )

        # Step 4: Layer 2 - Domain merge: social_profile (LN+X)
        if ln_data:
            social_merged, social_decisions = merge_social_fields(ln_data)
            await self._storage.upsert_social_profile(
                dp_id, social_merged, linkedin_url=linkedin_url
            )
            await self._storage.write_merge_audit(
                dp_id, "domain_social", "social_profile", merge_run_id, social_decisions
            )
            social_for_agg = social_merged
        else:
            social_for_agg = {}

        # Step 5: Layer 3 - Aggregated merge
        agg_merged, agg_decisions = merge_aggregated_fields(dev_merged, social_for_agg)
        await self._storage.upsert_aggregated_individual_profile(dp_id, agg_merged)
        await self._storage.write_merge_audit(
            dp_id, "aggregation", "aggregated_individual_profile",
            merge_run_id, agg_decisions,
        )

        # Step 6: Layer 4 - Cohesive enrichment
        coh_merged, coh_decisions = merge_cohesive_fields(agg_merged)
        embedding_text = build_embedding_text(coh_merged)
        await self._storage.upsert_cohesive_individual_profile(
            dp_id, coh_merged, embedding_text=embedding_text
        )
        await self._storage.write_merge_audit(
            dp_id, "cohesive", "cohesive_individual_profile",
            merge_run_id, coh_decisions,
        )

        # Step 7: Index to search engines (Qdrant + OpenSearch)
        if self._indexer:
            try:
                profile_data = {
                    **coh_merged,
                    "developer_profile_id": dp_id,
                    "embedding_text": embedding_text,
                }
                await self._indexer.index_profile(profile_data)
            except Exception:
                log.exception("Failed to index profile for %s", dp_id)
