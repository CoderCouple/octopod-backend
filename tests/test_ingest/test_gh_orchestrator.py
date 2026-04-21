"""Tests for GH orchestrator — mocked client and storage."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ingest.common.errors import PermanentError, TransientError
from app.ingest.gh.orchestrator import GHOrchestrator, IngestStats


def _make_config():
    config = MagicMock()
    config.concurrency = 2
    config.refresh_after_hours = 24
    config.skip_forks = True
    return config


def _make_user_bundle(login="testuser", db_id=12345):
    return {
        "databaseId": db_id,
        "login": login,
        "name": "Test User",
        "repositories": {
            "nodes": [
                {
                    "databaseId": 1,
                    "name": "repo1",
                    "nameWithOwner": f"{login}/repo1",
                    "isFork": False,
                    "isArchived": False,
                    "stargazerCount": 10,
                    "defaultBranchRef": {
                        "target": {
                            "history": {
                                "nodes": [
                                    {"oid": "abc123", "message": "init"}
                                ]
                            }
                        }
                    },
                }
            ]
        },
    }


@pytest.mark.asyncio
async def test_orchestrator_success():
    config = _make_config()
    client = AsyncMock()
    client.fetch_user_bundle = AsyncMock(return_value=_make_user_bundle())
    client.fetch_user_events = AsyncMock(return_value=[])

    storage = AsyncMock()
    storage.recently_ingested = AsyncMock(return_value=False)
    storage.upsert_user = AsyncMock(return_value=12345)
    storage.upsert_repos = AsyncMock(return_value=[1])
    storage.upsert_commits = AsyncMock(return_value=1)
    storage.upsert_events = AsyncMock(return_value=0)
    storage.mark_checkpoint = AsyncMock()

    orch = GHOrchestrator(config, client, storage)
    stats = await orch.run(["testuser"])

    assert stats.succeeded == 1
    assert stats.failed == 0
    assert stats.processed == 1
    storage.upsert_user.assert_called_once()
    storage.mark_checkpoint.assert_called_with("testuser", "success", job_id=None)


@pytest.mark.asyncio
async def test_orchestrator_skips_recently_ingested():
    config = _make_config()
    client = AsyncMock()
    storage = AsyncMock()
    storage.recently_ingested = AsyncMock(return_value=True)

    orch = GHOrchestrator(config, client, storage)
    stats = await orch.run(["testuser"])

    assert stats.skipped == 1
    assert stats.succeeded == 0
    client.fetch_user_bundle.assert_not_called()


@pytest.mark.asyncio
async def test_orchestrator_handles_permanent_error():
    config = _make_config()
    client = AsyncMock()
    client.fetch_user_bundle = AsyncMock(side_effect=PermanentError("404"))

    storage = AsyncMock()
    storage.recently_ingested = AsyncMock(return_value=False)
    storage.mark_checkpoint = AsyncMock()

    orch = GHOrchestrator(config, client, storage)
    stats = await orch.run(["gone_user"])

    assert stats.permanent_errors == 1
    assert stats.failed == 1
    storage.mark_checkpoint.assert_called_with("gone_user", "failed", "404", job_id=None)


@pytest.mark.asyncio
async def test_orchestrator_handles_transient_error():
    config = _make_config()
    client = AsyncMock()
    client.fetch_user_bundle = AsyncMock(side_effect=TransientError("timeout"))

    storage = AsyncMock()
    storage.recently_ingested = AsyncMock(return_value=False)
    storage.mark_checkpoint = AsyncMock()

    orch = GHOrchestrator(config, client, storage)
    stats = await orch.run(["flaky_user"])

    assert stats.transient_errors == 1
    assert stats.failed == 1
    storage.mark_checkpoint.assert_called_with("flaky_user", "pending", "timeout", job_id=None)


@pytest.mark.asyncio
async def test_orchestrator_multiple_users():
    config = _make_config()
    client = AsyncMock()
    client.fetch_user_bundle = AsyncMock(
        side_effect=[_make_user_bundle("a", 1), _make_user_bundle("b", 2)]
    )
    client.fetch_user_events = AsyncMock(return_value=[])

    storage = AsyncMock()
    storage.recently_ingested = AsyncMock(return_value=False)
    storage.upsert_user = AsyncMock(side_effect=[1, 2])
    storage.upsert_repos = AsyncMock(return_value=[])
    storage.upsert_commits = AsyncMock(return_value=0)
    storage.upsert_events = AsyncMock(return_value=0)
    storage.mark_checkpoint = AsyncMock()

    orch = GHOrchestrator(config, client, storage)
    stats = await orch.run(["a", "b"])

    assert stats.succeeded == 2
    assert stats.processed == 2


def test_ingest_stats_summary():
    stats = IngestStats(processed=10, succeeded=8, failed=2, skipped=1)
    s = stats.summary()
    assert "processed=10" in s
    assert "ok=8" in s
