"""Unified pipeline runner with control loop, tracking, and step dispatch."""
from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from app.common.enum.ingest import (
    ControlSignal,
    IngestJobType,
    IngestTrigger,
    PipelineStatus,
    PipelineType,
)
from app.ingest.common.job_tracker import JobTracker

from .steps import get_steps
from .tracker import PipelineTracker

log = logging.getLogger(__name__)


class PipelineRunner:
    """Orchestrates multi-step ingestion pipelines with pause/cancel support."""

    def __init__(self, pool: Any) -> None:
        self._pool = pool
        self._discovered_logins: list[str] = []
        self._discovered_hf_usernames: list[str] = []

    async def run(
        self,
        pipeline_type: str,
        trigger: str = "cli",
        triggered_by: str | None = None,
        input_params: dict[str, Any] | None = None,
        resume_from_step: int | None = None,
    ) -> dict[str, Any]:
        """Run a full pipeline with control signal checks between steps."""
        params = input_params or {}
        steps = get_steps(pipeline_type)
        pt = PipelineTracker(self._pool)

        # Concurrency guard: full pipelines block each other;
        # individual runs (gh_only, hf_only, ln_only) can run in parallel with anything.
        _FULL_TYPES = {
            PipelineType.DAILY, PipelineType.WEEKLY,
            PipelineType.SEED, PipelineType.DEPENDENT,
        }
        is_full = PipelineType(pipeline_type) in _FULL_TYPES
        if is_full:
            active = await PipelineTracker.get_active_executions(self._pool)
            running_full = [
                e for e in active
                if e["status"] == PipelineStatus.RUNNING
                and PipelineType(e["pipeline_type"]) in _FULL_TYPES
            ]
            if running_full:
                raise RuntimeError(
                    f"Full pipeline {running_full[0]['id']} is already running. "
                    "Pause or cancel it first."
                )

        exec_id = await pt.create_execution(
            pipeline_type=pipeline_type,
            steps=steps,
            trigger=trigger,
            triggered_by=triggered_by,
            input_params=params,
        )
        await pt.mark_execution_running()

        results: dict[str, Any] = {"execution_id": exec_id, "steps": {}}

        try:
            for i, step_def in enumerate(steps, start=1):
                # Skip already-completed steps on resume
                if resume_from_step and i < resume_from_step:
                    continue

                # Check control signal between steps
                signal = await pt.check_control_signal()
                if signal == ControlSignal.CANCEL:
                    log.info("[%s] Cancel signal received, cancelling remaining steps", pipeline_type)
                    for j in range(i, len(steps) + 1):
                        await pt.mark_step_cancelled(j)
                    await pt.mark_execution_cancelled()
                    results["status"] = "cancelled"
                    return results

                if signal == ControlSignal.PAUSE:
                    log.info("[%s] Pause signal received at step %d", pipeline_type, i)
                    await pt.clear_control_signal()
                    await pt.mark_execution_paused()
                    results["status"] = "paused"
                    results["paused_at_step"] = i
                    return results

                # Execute step
                step_name = step_def["name"]
                log.info("[%s] Step %d/%d: %s", pipeline_type, i, len(steps), step_name)
                await pt.mark_step_running(i)

                try:
                    step_result = await self._execute_step(
                        step_name, params, pt, i, pipeline_type, exec_id
                    )
                    await pt.mark_step_completed(i, step_result)
                    results["steps"][step_name] = step_result
                except Exception as e:
                    log.exception("[%s] Step %s failed", pipeline_type, step_name)
                    await pt.mark_step_failed(i, str(e))
                    await pt.mark_execution_failed(str(e))
                    results["error"] = str(e)
                    results["failed_step"] = step_name
                    return results

            await pt.mark_execution_completed()
            results["status"] = "completed"
            log.info("[%s] Pipeline completed: %s", pipeline_type, exec_id)

        except Exception as e:
            log.exception("[%s] Pipeline failed unexpectedly", pipeline_type)
            await pt.mark_execution_failed(str(e))
            results["error"] = str(e)

        return results

    async def _execute_step(
        self,
        step_name: str,
        params: dict[str, Any],
        pt: PipelineTracker,
        step_order: int,
        pipeline_type: str,
        exec_id: str,
    ) -> dict[str, Any]:
        """Dispatch to the appropriate step implementation."""
        dispatch = {
            "gh_discover": self._step_gh_discover,
            "gh_ingest": self._step_gh_ingest,
            "hf_discover": self._step_hf_discover,
            "hf_ingest": self._step_hf_ingest,
            "hf_crossref": self._step_hf_crossref,
            "ln_discover": self._step_ln_discover,
            "ln_ingest": self._step_ln_ingest,
            "ln_crossref": self._step_ln_crossref,
            "identity_resolve": self._step_identity_resolve,
            "bridge_sync": self._step_bridge_sync,
            "embed": self._step_embed,
        }
        handler = dispatch.get(step_name)
        if not handler:
            raise ValueError(f"Unknown step: {step_name}")
        return await handler(params, pt, step_order, exec_id)

    # ---- Step implementations ----

    async def _step_gh_discover(
        self, params: dict[str, Any], pt: PipelineTracker, step_order: int, exec_id: str
    ) -> dict[str, Any]:
        from app.ingest.gh.config import GHConfig
        from app.ingest.gh.discover import discover_top_users

        config = GHConfig()
        config.validate()

        ranked = await discover_top_users(
            config,
            n=params.get("top", 5000),
            alpha=params.get("alpha", 0.5),
            languages=params.get("languages"),
            topics=params.get("topics"),
            min_repos=params.get("min_repos"),
            min_followers=params.get("min_followers"),
        )
        self._discovered_logins = [u.login for u in ranked]
        await pt.update_step_progress(step_order, len(ranked), len(ranked), 0)
        return {"total": len(ranked), "succeeded": len(ranked), "failed": 0}

    async def _step_gh_ingest(
        self, params: dict[str, Any], pt: PipelineTracker, step_order: int, exec_id: str
    ) -> dict[str, Any]:
        from app.ingest.gh.client import GitHubClient
        from app.ingest.gh.config import GHConfig
        from app.ingest.gh.orchestrator import GHOrchestrator
        from app.ingest.gh.storage import GHStorage
        from app.ingest.gh.token_pool import TokenPool

        logins = params.get("logins") or self._discovered_logins
        if not logins:
            return {"total": 0, "succeeded": 0, "failed": 0, "skipped": 0}

        config = GHConfig()
        config.validate()
        token_pool = TokenPool(config.github_tokens)

        tracker = JobTracker(self._pool, "github")
        job_id = await tracker.create_job(
            job_type=IngestJobType.GH_INGEST,
            trigger=IngestTrigger.CLI,
            triggered_by="pipeline",
            input_params={"total_logins": len(logins)},
            execution_phase_id=exec_id,
        )
        await tracker.mark_running()
        await pt.mark_step_running(step_order, job_id)

        storage = GHStorage(config.db_dsn, config.db_pool_min, config.db_pool_max)
        await storage.connect()
        try:
            async with GitHubClient(config, token_pool) as client:
                orch = GHOrchestrator(config, client, storage, job_tracker=tracker)
                stats = await orch.run(logins)
                result = asdict(stats)
                await tracker.mark_completed(result)
                return result
        finally:
            await storage.close()

    async def _step_hf_discover(
        self, params: dict[str, Any], pt: PipelineTracker, step_order: int, exec_id: str
    ) -> dict[str, Any]:
        from app.ingest.hf.config import HFConfig
        from app.ingest.hf.discover import discover_top_authors

        config = HFConfig()
        config.validate()

        ranked = await discover_top_authors(
            config,
            n=params.get("hf_top", params.get("top", 5000)),
            alpha=params.get("hf_alpha", params.get("alpha", 0.5)),
            pipeline_tag=params.get("hf_pipeline_tag"),
            library=params.get("hf_library"),
        )
        self._discovered_hf_usernames = [a.username for a in ranked]
        await pt.update_step_progress(step_order, len(ranked), len(ranked), 0)
        return {"total": len(ranked), "succeeded": len(ranked), "failed": 0}

    async def _step_hf_ingest(
        self, params: dict[str, Any], pt: PipelineTracker, step_order: int, exec_id: str
    ) -> dict[str, Any]:
        from app.ingest.hf.client import HFClient
        from app.ingest.hf.config import HFConfig
        from app.ingest.hf.orchestrator import HFOrchestrator
        from app.ingest.hf.storage import HFStorage

        usernames = params.get("hf_usernames") or self._discovered_hf_usernames
        if not usernames:
            return {"total": 0, "succeeded": 0, "failed": 0, "skipped": 0}

        config = HFConfig()
        config.validate()

        tracker = JobTracker(self._pool, "huggingface")
        job_id = await tracker.create_job(
            job_type=IngestJobType.HF_INGEST,
            trigger=IngestTrigger.CLI,
            triggered_by="pipeline",
            input_params={"total_usernames": len(usernames)},
            execution_phase_id=exec_id,
        )
        await tracker.mark_running()
        await pt.mark_step_running(step_order, job_id)

        storage = HFStorage(config.db_dsn, config.db_pool_min, config.db_pool_max)
        await storage.connect()
        try:
            async with HFClient(config) as client:
                orch = HFOrchestrator(config, client, storage, job_tracker=tracker)
                stats = await orch.run(usernames)
                result = asdict(stats)
                await tracker.mark_completed(result)
                return result
        finally:
            await storage.close()

    async def _step_ln_discover(
        self, params: dict[str, Any], pt: PipelineTracker, step_order: int, exec_id: str
    ) -> dict[str, Any]:
        from app.ingest.bridge.config import BridgeConfig
        from app.ingest.bridge.storage import BridgeStorage
        from app.ingest.ln.config import LNConfig
        from app.ingest.ln.discover import discover_linkedin_urls
        from app.ingest.ln.storage import LNStorage

        ln_config = LNConfig()
        ln_config.validate()

        bridge_config = BridgeConfig()
        bridge_storage = BridgeStorage(
            bridge_config.db_dsn, bridge_config.db_pool_min, bridge_config.db_pool_max
        )
        await bridge_storage.connect()
        ln_storage = LNStorage(ln_config.db_dsn, ln_config.db_pool_min, ln_config.db_pool_max)
        await ln_storage.connect()
        try:
            count = await discover_linkedin_urls(bridge_storage, ln_storage)
            await pt.update_step_progress(step_order, count, count, 0)
            return {"total": count, "succeeded": count, "failed": 0}
        finally:
            await bridge_storage.close()
            await ln_storage.close()

    async def _step_ln_ingest(
        self, params: dict[str, Any], pt: PipelineTracker, step_order: int, exec_id: str
    ) -> dict[str, Any]:
        from app.ingest.ln.client import ProxycurlClient
        from app.ingest.ln.config import LNConfig
        from app.ingest.ln.orchestrator import LNOrchestrator
        from app.ingest.ln.storage import LNStorage

        config = LNConfig()
        config.validate()

        tracker = JobTracker(self._pool, "linkedin")
        job_id = await tracker.create_job(
            job_type=IngestJobType.LN_INGEST,
            trigger=IngestTrigger.CLI,
            triggered_by="pipeline",
            input_params={"max_profiles": params.get("max_profiles", 5000)},
            execution_phase_id=exec_id,
        )
        await tracker.mark_running()
        await pt.mark_step_running(step_order, job_id)

        storage = LNStorage(config.db_dsn, config.db_pool_min, config.db_pool_max)
        await storage.connect()
        try:
            async with ProxycurlClient(config) as client:
                orch = LNOrchestrator(config, client, storage, job_tracker=tracker)
                stats = await orch.run(max_profiles=params.get("max_profiles", 5000))
                result = {
                    "processed": stats.processed,
                    "succeeded": stats.succeeded,
                    "failed": stats.failed,
                    "budget_spent": stats.budget_spent,
                }
                await tracker.mark_completed(result)
                return result
        finally:
            await storage.close()

    async def _step_hf_crossref(
        self, params: dict[str, Any], pt: PipelineTracker, step_order: int, exec_id: str
    ) -> dict[str, Any]:
        """Cross-reference: find HF users matching discovered GH logins."""
        logins = self._discovered_logins
        if not logins:
            return {"total": 0, "succeeded": 0, "failed": 0}

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT username FROM hf_users WHERE github_username = ANY($1::text[])",
                logins,
            )
        self._discovered_hf_usernames = [r["username"] for r in rows]
        count = len(self._discovered_hf_usernames)
        await pt.update_step_progress(step_order, count, count, 0)
        log.info("[hf_crossref] Found %d HF users matching %d GH logins", count, len(logins))
        return {"total": count, "succeeded": count, "failed": 0}

    async def _step_ln_crossref(
        self, params: dict[str, Any], pt: PipelineTracker, step_order: int, exec_id: str
    ) -> dict[str, Any]:
        """Cross-reference: extract LinkedIn URLs from GH users' social_accounts, bio, website."""
        import re

        from app.ingest.ln.config import LNConfig
        from app.ingest.ln.storage import LNStorage

        logins = self._discovered_logins
        if not logins:
            return {"total": 0, "succeeded": 0, "failed": 0}

        linkedin_re = re.compile(r"linkedin\.com/in/([\w-]+)", re.IGNORECASE)
        pending: list[dict[str, Any]] = []

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT login, social_accounts, bio, website_url "
                "FROM gh_users WHERE login = ANY($1::text[])",
                logins,
            )

        for row in rows:
            found_urls: set[str] = set()

            # Check social_accounts JSONB for LinkedIn provider
            accounts = row["social_accounts"]
            if accounts:
                if isinstance(accounts, str):
                    import json

                    accounts = json.loads(accounts)
                if isinstance(accounts, list):
                    for acct in accounts:
                        if isinstance(acct, dict) and acct.get("provider", "").upper() == "LINKEDIN":
                            url = acct.get("url", "")
                            if url:
                                found_urls.add(url)

            # Check bio and website_url for linkedin.com/in/...
            for field in [row.get("bio") or "", row.get("website_url") or ""]:
                matches = linkedin_re.findall(field)
                for slug in matches:
                    found_urls.add(f"https://www.linkedin.com/in/{slug}")

            for url in found_urls:
                pending.append({
                    "linkedin_url": url,
                    "source_platform": "github",
                    "source_username": row["login"],
                    "priority": 2,
                })

        inserted = 0
        if pending:
            ln_config = LNConfig()
            ln_storage = LNStorage(ln_config.db_dsn, ln_config.db_pool_min, ln_config.db_pool_max)
            await ln_storage.connect()
            try:
                inserted = await ln_storage.upsert_pending_urls(pending)
            finally:
                await ln_storage.close()

        await pt.update_step_progress(step_order, len(pending), inserted, 0)
        log.info("[ln_crossref] Found %d LinkedIn URLs from %d GH users", len(pending), len(logins))
        return {"total": len(pending), "succeeded": inserted, "failed": 0}

    async def _step_identity_resolve(
        self, params: dict[str, Any], pt: PipelineTracker, step_order: int, exec_id: str
    ) -> dict[str, Any]:
        from app.ingest.bridge.resolver import IdentityResolver

        resolver = IdentityResolver(self._pool)
        stats = await resolver.run(
            since_hours=params.get("since_hours", 24),
            full_scan=params.get("full_scan", False),
        )
        result = {
            "total": stats.total_candidates,
            "auto_merged": stats.auto_merged,
            "queued_for_review": stats.queued_for_review,
            "skipped": stats.skipped,
            "errors": stats.errors,
        }
        await pt.update_step_progress(
            step_order, stats.total_candidates, stats.auto_merged, stats.errors
        )
        return result

    async def _step_bridge_sync(
        self, params: dict[str, Any], pt: PipelineTracker, step_order: int, exec_id: str
    ) -> dict[str, Any]:
        from app.ingest.bridge.config import BridgeConfig
        from app.ingest.bridge.orchestrator import BridgeOrchestrator
        from app.ingest.bridge.storage import BridgeStorage

        bridge_config = BridgeConfig()
        storage = BridgeStorage(
            bridge_config.db_dsn, bridge_config.db_pool_min, bridge_config.db_pool_max
        )
        await storage.connect()
        try:
            from app.db.qdrant_client import get_qdrant_client
            from app.ingest.bridge.indexer import DualIndexer
            from app.service.embedding.sentence_transformer_provider import (
                SentenceTransformerProvider,
            )

            qdrant_client = get_qdrant_client()
            embedding_provider = SentenceTransformerProvider()
            indexer = DualIndexer(
                qdrant_client=qdrant_client,
                embedding_provider=embedding_provider,
            )

            orch = BridgeOrchestrator(bridge_config, storage, indexer=indexer)
            mode = params.get("sync_mode", "recent")
            since_hours = params.get("since_hours", 24)
            stats = await orch.run(mode=mode, since_hours=since_hours)
            result = {
                "total": stats.processed,
                "processed": stats.processed,
                "succeeded": stats.succeeded,
                "failed": stats.failed,
            }
            await pt.update_step_progress(
                step_order, stats.processed, stats.succeeded, stats.failed
            )
            return result
        finally:
            await storage.close()

    async def _step_embed(
        self, params: dict[str, Any], pt: PipelineTracker, step_order: int, exec_id: str
    ) -> dict[str, Any]:
        from app.db.qdrant_client import get_qdrant_client
        from app.ingest.bridge.indexer import DualIndexer
        from app.ingest.pipeline.embed import batch_embed_from_db
        from app.service.embedding.sentence_transformer_provider import SentenceTransformerProvider

        qdrant_client = get_qdrant_client()
        embedding_provider = SentenceTransformerProvider()
        indexer = DualIndexer(
            qdrant_client=qdrant_client,
            embedding_provider=embedding_provider,
        )

        stats = await batch_embed_from_db(
            pool=self._pool,
            indexer=indexer,
            batch_size=params.get("batch_size", 200),
            force=params.get("force_embed", False),
            pipeline_tracker=pt,
            step_order=step_order,
        )
        return {
            "total": stats["total"],
            "succeeded": stats["embedded"],
            "failed": stats["errors"],
            "skipped": stats["skipped"],
        }

    # ---- Legacy convenience methods ----

    async def run_daily(self, input_params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self.run("daily", trigger="cli", triggered_by="pipeline", input_params=input_params)

    async def run_weekly(self, input_params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self.run("weekly", trigger="cli", triggered_by="pipeline", input_params=input_params)
