"""Tests for HF orchestrator — mocked client and storage."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ingest.common.errors import PermanentError, TransientError
from app.ingest.hf.orchestrator import HFOrchestrator, IngestStats


def _make_config():
    config = MagicMock()
    config.concurrency = 2
    config.refresh_after_hours = 24
    return config


@pytest.mark.asyncio
async def test_hf_orchestrator_success():
    config = _make_config()
    client = AsyncMock()
    client.fetch_user = AsyncMock(return_value={"_type": "user", "fullname": "Test"})
    client.list_models = AsyncMock(return_value=[{"id": "test/model1"}])
    client.list_datasets = AsyncMock(return_value=[])

    storage = AsyncMock()
    storage.recently_ingested = AsyncMock(return_value=False)
    storage.upsert_user = AsyncMock(return_value="testuser")
    storage.upsert_models = AsyncMock(return_value=1)
    storage.upsert_datasets = AsyncMock(return_value=0)
    storage.mark_checkpoint = AsyncMock()

    orch = HFOrchestrator(config, client, storage)
    stats = await orch.run(["testuser"])

    assert stats.succeeded == 1
    assert stats.total_models == 1
    storage.mark_checkpoint.assert_called_with("testuser", "success", job_id=None)


@pytest.mark.asyncio
async def test_hf_orchestrator_skips_recently_ingested():
    config = _make_config()
    client = AsyncMock()
    storage = AsyncMock()
    storage.recently_ingested = AsyncMock(return_value=True)

    orch = HFOrchestrator(config, client, storage)
    stats = await orch.run(["testuser"])

    assert stats.skipped == 1
    client.fetch_user.assert_not_called()


@pytest.mark.asyncio
async def test_hf_orchestrator_permanent_error():
    config = _make_config()
    client = AsyncMock()
    client.fetch_user = AsyncMock(side_effect=PermanentError("404"))

    storage = AsyncMock()
    storage.recently_ingested = AsyncMock(return_value=False)
    storage.mark_checkpoint = AsyncMock()

    orch = HFOrchestrator(config, client, storage)
    stats = await orch.run(["gone"])

    assert stats.permanent_errors == 1
    assert stats.failed == 1


@pytest.mark.asyncio
async def test_hf_orchestrator_transient_error():
    config = _make_config()
    client = AsyncMock()
    client.fetch_user = AsyncMock(side_effect=TransientError("timeout"))

    storage = AsyncMock()
    storage.recently_ingested = AsyncMock(return_value=False)
    storage.mark_checkpoint = AsyncMock()

    orch = HFOrchestrator(config, client, storage)
    stats = await orch.run(["flaky"])

    assert stats.transient_errors == 1
    assert stats.failed == 1


def test_hf_ingest_stats_summary():
    stats = IngestStats(
        processed=10, succeeded=8, failed=2, total_models=50, total_datasets=20
    )
    s = stats.summary()
    assert "processed=10" in s
    assert "models=50" in s
