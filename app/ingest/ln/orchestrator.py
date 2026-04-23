"""LinkedIn ingestion orchestrator with budget-aware stopping."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from app.ingest.common.job_tracker import JobTracker
from app.ingest.ln.client import ProxycurlClient
from app.ingest.ln.config import LNConfig
from app.ingest.ln.storage import LNStorage

log = logging.getLogger(__name__)


@dataclass
class LNStats:
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    budget_spent: float = 0.0


class LNOrchestrator:
    def __init__(
        self,
        config: LNConfig,
        client: ProxycurlClient,
        storage: LNStorage,
        job_tracker: JobTracker | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._storage = storage
        self._tracker = job_tracker

    async def run(
        self,
        urls: list[str] | None = None,
        max_profiles: int | None = None,
    ) -> LNStats:
        """Ingest LinkedIn profiles.

        Args:
            urls: Specific URLs to ingest. If None, reads from ln_pending_urls.
            max_profiles: Maximum profiles to process before stopping.
        """
        if urls is None:
            limit = max_profiles or 5000
            urls = await self._storage.list_pending_urls(limit=limit)

        if max_profiles:
            urls = urls[:max_profiles]

        stats = LNStats()
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        for url in urls:
            await queue.put(url)
        for _ in range(self._config.concurrency):
            await queue.put(None)

        workers = [
            asyncio.create_task(self._worker(queue, stats))
            for _ in range(self._config.concurrency)
        ]
        await asyncio.gather(*workers)
        stats.budget_spent = self._client._budget_spent
        return stats

    async def _worker(
        self, queue: asyncio.Queue, stats: LNStats
    ) -> None:
        while True:
            url = await queue.get()
            if url is None:
                break

            # Budget check
            if self._client.budget_exhausted:
                stats.skipped += 1
                log.warning("Budget exhausted, skipping %s", url)
                continue

            try:
                if self._tracker:
                    await self._tracker.item_started(url)

                # Skip recently ingested
                if await self._storage.recently_ingested(url, within_hours=24 * 7):
                    stats.skipped += 1
                    if self._tracker:
                        await self._tracker.item_skipped(url)
                    continue

                # Mark as in-progress
                await self._storage.mark_pending_url_status(url, "ingesting")

                # Fetch from Proxycurl
                profile = await self._client.fetch_profile(url)
                if profile is None:
                    stats.failed += 1
                    await self._storage.mark_checkpoint(url, "failed", "No data returned")
                    await self._storage.mark_pending_url_status(url, "failed")
                    if self._tracker:
                        await self._tracker.item_failed(url, "NoData", "Profile not found")
                    continue

                # Store
                await self._storage.upsert_user(url, profile)
                await self._storage.mark_checkpoint(
                    url, "success",
                    job_id=self._tracker.job_id if self._tracker else None,
                )
                await self._storage.mark_pending_url_status(url, "completed")

                stats.processed += 1
                stats.succeeded += 1
                if self._tracker:
                    await self._tracker.item_completed(url, {"ln_users": 1})

            except Exception as e:
                stats.processed += 1
                stats.failed += 1
                log.exception("Failed to ingest %s", url)
                await self._storage.mark_checkpoint(url, "failed", str(e)[:500])
                await self._storage.mark_pending_url_status(url, "failed")
                if self._tracker:
                    await self._tracker.item_failed(url, type(e).__name__, str(e)[:500])
