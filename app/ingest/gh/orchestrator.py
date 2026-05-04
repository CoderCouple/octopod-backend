"""
Orchestrator: pulls logins from an async queue, fans out work across a worker
pool, and writes results to Postgres. Handles per-user errors independently
so one bad profile doesn't stall the run.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from dataclasses import dataclass

from app.common.enum.ingest import ControlSignal
from app.ingest.common.errors import PermanentError, TransientError
from app.ingest.common.job_tracker import JobTracker

from .client import GitHubClient
from .config import GHConfig
from .storage import GHStorage

log = logging.getLogger(__name__)


@dataclass
class IngestStats:
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    permanent_errors: int = 0
    transient_errors: int = 0

    def summary(self) -> str:
        return (
            f"processed={self.processed} ok={self.succeeded} "
            f"failed={self.failed} skipped={self.skipped} "
            f"permanent={self.permanent_errors} transient={self.transient_errors}"
        )


class GHOrchestrator:
    def __init__(
        self,
        config: GHConfig,
        client: GitHubClient,
        storage: GHStorage,
        job_tracker: JobTracker | None = None,
    ) -> None:
        self.config = config
        self.client = client
        self.storage = storage
        self.tracker = job_tracker
        self.stats = IngestStats()
        self._cancelled = False

    async def run(self, logins: Iterable[str]) -> IngestStats:
        queue: asyncio.Queue[str | None] = asyncio.Queue(
            maxsize=self.config.concurrency * 4
        )

        producer = asyncio.create_task(self._producer(logins, queue))
        workers = [
            asyncio.create_task(self._worker(i, queue))
            for i in range(self.config.concurrency)
        ]

        await producer
        for _ in workers:
            await queue.put(None)
        await asyncio.gather(*workers)

        if self._cancelled and self.tracker:
            await self.tracker.mark_cancelled()

        log.info("GH ingestion complete: %s", self.stats.summary())
        return self.stats

    async def _producer(
        self, logins: Iterable[str], queue: asyncio.Queue
    ) -> None:
        for login in logins:
            if self._cancelled:
                return
            login = login.strip()
            if not login:
                continue
            await queue.put(login)

    async def _worker(self, worker_id: int, queue: asyncio.Queue) -> None:
        while True:
            login = await queue.get()
            if login is None:
                return
            try:
                await self._process_one(login)
            except Exception as e:
                log.exception(
                    "Worker %d: unhandled error on %s: %s", worker_id, login, e
                )
                self.stats.failed += 1
            finally:
                self.stats.processed += 1
                if self.stats.processed % 50 == 0:
                    log.info("Progress: %s", self.stats.summary())

            # Check control signal after each item
            if self.tracker:
                signal = await self.tracker.check_control_signal()
                if signal == ControlSignal.CANCEL:
                    self._cancelled = True
                    return
                if signal == ControlSignal.PAUSE:
                    await self.tracker.mark_paused()
                    while True:
                        await asyncio.sleep(5)
                        signal = await self.tracker.check_control_signal()
                        if signal == ControlSignal.CANCEL:
                            self._cancelled = True
                            return
                        if signal == ControlSignal.NONE:
                            await self.tracker.mark_resumed()
                            break

    async def _process_one(self, login: str) -> None:
        if await self.storage.recently_ingested(
            login, self.config.refresh_after_hours
        ):
            log.debug("Skipping %s (recently ingested)", login)
            self.stats.skipped += 1
            if self.tracker:
                await self.tracker.item_skipped(login)
            return

        if self.tracker:
            await self.tracker.item_started(login)

        try:
            user = await self.client.fetch_user_bundle(login)
        except PermanentError as e:
            log.info("Permanent error for %s: %s", login, e)
            await self.storage.mark_checkpoint(
                login, "failed", str(e), job_id=self.tracker.job_id if self.tracker else None
            )
            self.stats.permanent_errors += 1
            self.stats.failed += 1
            if self.tracker:
                await self.tracker.item_failed(login, "permanent", str(e))
            return
        except TransientError as e:
            log.warning("Transient error for %s: %s", login, e)
            await self.storage.mark_checkpoint(
                login, "pending", str(e), job_id=self.tracker.job_id if self.tracker else None
            )
            self.stats.transient_errors += 1
            self.stats.failed += 1
            if self.tracker:
                await self.tracker.item_failed(login, "transient", str(e))
            return

        user_id = await self.storage.upsert_user(user)

        repos = (user.get("repositories") or {}).get("nodes") or []
        if self.config.skip_forks:
            repos = [r for r in repos if r and not r.get("isFork")]

        await self.storage.upsert_repos(user_id, repos)

        total_commits = 0
        for repo in repos:
            ref = repo.get("defaultBranchRef") or {}
            target = ref.get("target") or {}
            history = (target.get("history") or {}).get("nodes") or []
            if history:
                total_commits += await self.storage.upsert_commits(
                    repo["databaseId"], history
                )

        # Activity events (separate REST call; best-effort)
        n_events = 0
        try:
            events = await self.client.fetch_user_events(login)
            n_events = await self.storage.upsert_events(user_id, events)
        except (PermanentError, TransientError) as e:
            log.debug("Events fetch failed for %s: %s", login, e)

        await self.storage.mark_checkpoint(
            login, "success", job_id=self.tracker.job_id if self.tracker else None
        )
        self.stats.succeeded += 1
        if self.tracker:
            await self.tracker.item_completed(
                login, {"repos": len(repos), "commits": total_commits, "events": n_events}
            )
        log.debug(
            "Ingested %s: %d repos, %d commits", login, len(repos), total_commits
        )
