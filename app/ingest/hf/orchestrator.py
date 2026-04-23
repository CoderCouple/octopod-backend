"""HF orchestrator: parallel worker pool pulling usernames from a queue."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from dataclasses import dataclass

from app.ingest.common.errors import PermanentError, TransientError
from app.ingest.common.job_tracker import JobTracker

from .client import HFClient
from .config import HFConfig
from .storage import HFStorage

log = logging.getLogger(__name__)


@dataclass
class IngestStats:
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    permanent_errors: int = 0
    transient_errors: int = 0
    total_models: int = 0
    total_datasets: int = 0

    def summary(self) -> str:
        return (
            f"processed={self.processed} ok={self.succeeded} "
            f"failed={self.failed} skipped={self.skipped} "
            f"models={self.total_models} datasets={self.total_datasets}"
        )


class HFOrchestrator:
    def __init__(
        self,
        config: HFConfig,
        client: HFClient,
        storage: HFStorage,
        job_tracker: JobTracker | None = None,
    ) -> None:
        self.config = config
        self.client = client
        self.storage = storage
        self.tracker = job_tracker
        self.stats = IngestStats()

    async def run(self, usernames: Iterable[str]) -> IngestStats:
        queue: asyncio.Queue[str | None] = asyncio.Queue(
            maxsize=self.config.concurrency * 4
        )

        producer = asyncio.create_task(self._producer(usernames, queue))
        workers = [
            asyncio.create_task(self._worker(i, queue))
            for i in range(self.config.concurrency)
        ]

        await producer
        for _ in workers:
            await queue.put(None)
        await asyncio.gather(*workers)

        log.info("HF ingestion complete: %s", self.stats.summary())
        return self.stats

    async def _producer(
        self, usernames: Iterable[str], queue: asyncio.Queue
    ) -> None:
        for u in usernames:
            u = u.strip()
            if u:
                await queue.put(u)

    async def _worker(self, worker_id: int, queue: asyncio.Queue) -> None:
        while True:
            username = await queue.get()
            if username is None:
                return
            try:
                await self._process_one(username)
            except Exception as e:
                log.exception(
                    "HF worker %d: unhandled error on %s: %s",
                    worker_id,
                    username,
                    e,
                )
                self.stats.failed += 1
            finally:
                self.stats.processed += 1
                if self.stats.processed % 50 == 0:
                    log.info("Progress: %s", self.stats.summary())

    async def _process_one(self, username: str) -> None:
        if await self.storage.recently_ingested(
            username, self.config.refresh_after_hours
        ):
            log.debug("Skipping %s (recently ingested)", username)
            self.stats.skipped += 1
            if self.tracker:
                await self.tracker.item_skipped(username)
            return

        if self.tracker:
            await self.tracker.item_started(username)

        try:
            user = await self.client.fetch_user(username)
        except PermanentError as e:
            log.info("Permanent error for %s: %s", username, e)
            await self.storage.mark_checkpoint(
                username, "failed", str(e), job_id=self.tracker.job_id if self.tracker else None
            )
            self.stats.permanent_errors += 1
            self.stats.failed += 1
            if self.tracker:
                await self.tracker.item_failed(username, "permanent", str(e))
            return
        except TransientError as e:
            log.warning("Transient error for %s: %s", username, e)
            await self.storage.mark_checkpoint(
                username, "pending", str(e), job_id=self.tracker.job_id if self.tracker else None
            )
            self.stats.transient_errors += 1
            self.stats.failed += 1
            if self.tracker:
                await self.tracker.item_failed(username, "transient", str(e))
            return

        # Skip organizations — we only want individual profiles
        if user.get("_type") == "org":
            log.debug("Skipping %s (organization, not individual)", username)
            self.stats.skipped += 1
            if self.tracker:
                await self.tracker.item_skipped(username)
            return

        await self.storage.upsert_user(username, user)

        # Models & datasets in parallel
        try:
            models_task = asyncio.create_task(self.client.list_models(username))
            datasets_task = asyncio.create_task(self.client.list_datasets(username))
            models, datasets = await asyncio.gather(models_task, datasets_task)
        except (PermanentError, TransientError) as e:
            log.warning("Listing failure for %s: %s", username, e)
            await self.storage.mark_checkpoint(
                username, "pending", str(e), job_id=self.tracker.job_id if self.tracker else None
            )
            self.stats.failed += 1
            if self.tracker:
                await self.tracker.item_failed(username, "transient", str(e))
            return

        n_models = await self.storage.upsert_models(username, models)
        n_datasets = await self.storage.upsert_datasets(username, datasets)
        self.stats.total_models += n_models
        self.stats.total_datasets += n_datasets

        await self.storage.mark_checkpoint(
            username, "success", job_id=self.tracker.job_id if self.tracker else None
        )
        self.stats.succeeded += 1
        if self.tracker:
            await self.tracker.item_completed(
                username, {"models": n_models, "datasets": n_datasets}
            )
        log.debug(
            "Ingested %s: %d models, %d datasets", username, n_models, n_datasets
        )
