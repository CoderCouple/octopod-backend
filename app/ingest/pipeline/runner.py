"""Unified pipeline runner: daily and weekly sequences."""
from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from app.common.enum.ingest import IngestJobType, IngestTrigger
from app.ingest.common.job_tracker import JobTracker

log = logging.getLogger(__name__)


class PipelineRunner:
    """Orchestrates multi-step ingestion pipelines."""

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def run_daily(self) -> dict[str, Any]:
        """Daily pipeline: GH discover → GH ingest → HF discover → HF ingest → Bridge sync.

        Returns summary dict.
        """
        tracker = JobTracker(self._pool, "pipeline")
        job_id = await tracker.create_job(
            job_type=IngestJobType.PIPELINE_DAILY,
            trigger=IngestTrigger.CLI,
            triggered_by="pipeline",
        )
        await tracker.mark_running()

        results: dict[str, Any] = {"job_id": job_id, "steps": {}}

        try:
            # Step 1: GH discover + ingest
            log.info("[daily] Step 1: GH discover")
            from app.ingest.gh.config import GHConfig
            from app.ingest.gh.discover import discover_top_users

            gh_config = GHConfig()
            gh_config.validate()
            ranked = await discover_top_users(gh_config, n=5000, alpha=0.5)
            results["steps"]["gh_discover"] = {"count": len(ranked)}

            log.info("[daily] Step 2: GH ingest (%d logins)", len(ranked))
            from app.ingest.gh.client import GitHubClient
            from app.ingest.gh.orchestrator import GHOrchestrator
            from app.ingest.gh.storage import GHStorage
            from app.ingest.gh.token_pool import TokenPool

            token_pool = TokenPool(gh_config.github_tokens)
            gh_storage = GHStorage(gh_config.db_dsn, gh_config.db_pool_min, gh_config.db_pool_max)
            await gh_storage.connect()
            try:
                async with GitHubClient(gh_config, token_pool) as client:
                    orch = GHOrchestrator(gh_config, client, gh_storage)
                    gh_stats = await orch.run([u.login for u in ranked])
                    results["steps"]["gh_ingest"] = asdict(gh_stats)
            finally:
                await gh_storage.close()

            # Step 3: HF discover + ingest
            log.info("[daily] Step 3: HF discover")
            from app.ingest.hf.config import HFConfig
            from app.ingest.hf.discover import discover_top_authors

            hf_config = HFConfig()
            hf_config.validate()
            hf_ranked = await discover_top_authors(hf_config, n=5000, alpha=0.5)
            results["steps"]["hf_discover"] = {"count": len(hf_ranked)}

            log.info("[daily] Step 4: HF ingest (%d usernames)", len(hf_ranked))
            from app.ingest.hf.client import HFClient
            from app.ingest.hf.orchestrator import HFOrchestrator
            from app.ingest.hf.storage import HFStorage

            hf_storage = HFStorage(hf_config.db_dsn, hf_config.db_pool_min, hf_config.db_pool_max)
            await hf_storage.connect()
            try:
                async with HFClient(hf_config) as hf_client:
                    hf_orch = HFOrchestrator(hf_config, hf_client, hf_storage)
                    hf_stats = await hf_orch.run([a.username for a in hf_ranked])
                    results["steps"]["hf_ingest"] = asdict(hf_stats)
            finally:
                await hf_storage.close()

            # Step 5: Bridge sync
            log.info("[daily] Step 5: Bridge sync")
            from app.ingest.bridge.config import BridgeConfig
            from app.ingest.bridge.orchestrator import BridgeOrchestrator
            from app.ingest.bridge.storage import BridgeStorage

            bridge_config = BridgeConfig()
            bridge_storage = BridgeStorage(
                bridge_config.db_dsn, bridge_config.db_pool_min, bridge_config.db_pool_max
            )
            await bridge_storage.connect()
            try:
                bridge_orch = BridgeOrchestrator(bridge_config, bridge_storage)
                sync_stats = await bridge_orch.run(mode="recent", since_hours=24)
                results["steps"]["bridge_sync"] = {
                    "processed": sync_stats.processed,
                    "succeeded": sync_stats.succeeded,
                    "failed": sync_stats.failed,
                }
            finally:
                await bridge_storage.close()

            await tracker.mark_completed(results["steps"])
            log.info("[daily] Pipeline completed: %s", results)

        except Exception as e:
            log.exception("[daily] Pipeline failed")
            await tracker.mark_failed(str(e))
            results["error"] = str(e)

        return results

    async def run_weekly(self) -> dict[str, Any]:
        """Weekly pipeline: LN discover → LN ingest → Bridge sync.

        Returns summary dict.
        """
        tracker = JobTracker(self._pool, "pipeline")
        job_id = await tracker.create_job(
            job_type=IngestJobType.PIPELINE_WEEKLY,
            trigger=IngestTrigger.CLI,
            triggered_by="pipeline",
        )
        await tracker.mark_running()

        results: dict[str, Any] = {"job_id": job_id, "steps": {}}

        try:
            # Step 1: LN discover
            log.info("[weekly] Step 1: LN discover")
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
                results["steps"]["ln_discover"] = {"count": count}

                # Step 2: LN ingest
                log.info("[weekly] Step 2: LN ingest")
                from app.ingest.ln.client import ProxycurlClient
                from app.ingest.ln.orchestrator import LNOrchestrator

                async with ProxycurlClient(ln_config) as client:
                    ln_orch = LNOrchestrator(ln_config, client, ln_storage)
                    ln_stats = await ln_orch.run(max_profiles=5000)
                    results["steps"]["ln_ingest"] = {
                        "processed": ln_stats.processed,
                        "succeeded": ln_stats.succeeded,
                        "failed": ln_stats.failed,
                        "budget_spent": ln_stats.budget_spent,
                    }

                # Step 3: Bridge sync with new LN data
                log.info("[weekly] Step 3: Bridge sync")
                from app.ingest.bridge.orchestrator import BridgeOrchestrator

                bridge_orch = BridgeOrchestrator(bridge_config, bridge_storage)
                sync_stats = await bridge_orch.run(mode="ln_only", since_hours=168)
                results["steps"]["bridge_sync"] = {
                    "processed": sync_stats.processed,
                    "succeeded": sync_stats.succeeded,
                    "failed": sync_stats.failed,
                }

            finally:
                await bridge_storage.close()
                await ln_storage.close()

            await tracker.mark_completed(results["steps"])
            log.info("[weekly] Pipeline completed: %s", results)

        except Exception as e:
            log.exception("[weekly] Pipeline failed")
            await tracker.mark_failed(str(e))
            results["error"] = str(e)

        return results
