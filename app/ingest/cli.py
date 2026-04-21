"""
CLI entry points for the ingestion engines.

Usage:
    python -m app.ingest.cli gh-discover --top 5000 --alpha 0.5 --output logins.txt
    python -m app.ingest.cli gh-ingest --input logins.txt --concurrency 8
    python -m app.ingest.cli gh-retry --status failed --max-attempts 3

    python -m app.ingest.cli hf-discover --top 5000 --alpha 0.5 --output usernames.txt
    python -m app.ingest.cli hf-ingest --input usernames.txt --concurrency 8
    python -m app.ingest.cli hf-retry --status failed --max-attempts 3

    python -m app.ingest.cli status
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import asdict
from pathlib import Path

from app.common.enum.ingest import IngestJobType, IngestTrigger

log = logging.getLogger(__name__)


def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s - %(message)s",
    )


def _load_logins(path: Path | None, inline: list[str]) -> list[str]:
    logins: list[str] = list(inline)
    if path:
        for line in path.read_text().splitlines():
            # Support TSV (login\trank\t...) — take first column
            stripped = line.strip().split("\t")[0].strip()
            if stripped:
                logins.append(stripped)
    seen: set[str] = set()
    out: list[str] = []
    for login in logins:
        if login not in seen:
            seen.add(login)
            out.append(login)
    return out


# ---- GitHub commands ----


async def _gh_discover(n: int, alpha: float, output: Path | None) -> int:
    from .common.job_tracker import JobTracker
    from .gh.config import GHConfig
    from .gh.discover import discover_top_users
    from .gh.storage import GHStorage

    config = GHConfig()
    config.validate()

    storage = GHStorage(config.db_dsn, config.db_pool_min, config.db_pool_max)
    await storage.connect()
    try:
        tracker = JobTracker(storage.pool, "github")
        job_id = await tracker.create_job(
            job_type=IngestJobType.GH_DISCOVER,
            trigger=IngestTrigger.CLI,
            triggered_by="cli",
            input_params={"top": n, "alpha": alpha},
        )
        await tracker.mark_running()
        log.info("Job %s started", job_id)

        ranked = await discover_top_users(config, n=n, alpha=alpha)
        await tracker.mark_completed({
            "processed": len(ranked),
            "succeeded": len(ranked),
            "failed": 0,
            "skipped": 0,
        })
    except Exception as e:
        await tracker.mark_failed(str(e))
        raise
    finally:
        await storage.close()

    lines = []
    for rank, u in enumerate(ranked, start=1):
        lines.append(
            f"{u.login}\t{rank}\t{u.followers}\t{u.total_stars}\t{u.score:.4f}"
        )
    body = "\n".join(lines) + "\n"
    if output:
        output.write_text(body)
        log.info("Wrote %d users to %s", len(ranked), output)
    else:
        for u in ranked:
            print(u.login)
    log.info("Job %s completed", job_id)
    return 0


async def _gh_ingest(logins: list[str], concurrency: int | None) -> int:
    from .common.job_tracker import JobTracker
    from .gh.client import GitHubClient
    from .gh.config import GHConfig
    from .gh.orchestrator import GHOrchestrator
    from .gh.storage import GHStorage
    from .gh.token_pool import TokenPool

    config = GHConfig()
    config.validate()
    if concurrency:
        config.concurrency = concurrency

    pool = TokenPool(config.github_tokens)
    storage = GHStorage(config.db_dsn, config.db_pool_min, config.db_pool_max)
    await storage.connect()
    try:
        tracker = JobTracker(storage.pool, "github")
        job_id = await tracker.create_job(
            job_type=IngestJobType.GH_INGEST,
            trigger=IngestTrigger.CLI,
            triggered_by="cli",
            input_params={"logins": logins[:100], "total_logins": len(logins)},
            concurrency=config.concurrency,
        )
        await tracker.mark_running()
        log.info("Job %s started (%d logins)", job_id, len(logins))

        async with GitHubClient(config, pool) as client:
            orch = GHOrchestrator(config, client, storage, job_tracker=tracker)
            stats = await orch.run(logins)
            await tracker.mark_completed(asdict(stats))
            log.info("Job %s completed", job_id)
            return 0 if stats.failed == 0 else 1
    except Exception as e:
        await tracker.mark_failed(str(e))
        raise
    finally:
        await storage.close()


async def _gh_retry(status_filter: str, max_attempts: int) -> int:
    import asyncpg

    from .common.job_tracker import JobTracker
    from .gh.client import GitHubClient
    from .gh.config import GHConfig
    from .gh.orchestrator import GHOrchestrator
    from .gh.storage import GHStorage
    from .gh.token_pool import TokenPool

    config = GHConfig()
    config.validate()

    conn = await asyncpg.connect(config.db_dsn)
    try:
        rows = await conn.fetch(
            "SELECT login FROM gh_checkpoints WHERE status = $1 AND attempt_count < $2",
            status_filter,
            max_attempts,
        )
    finally:
        await conn.close()

    logins = [r["login"] for r in rows]
    if not logins:
        log.info("No logins to retry (status=%s, max_attempts=%d)", status_filter, max_attempts)
        return 0

    log.info("Retrying %d logins with status=%s", len(logins), status_filter)
    pool = TokenPool(config.github_tokens)
    storage = GHStorage(config.db_dsn, config.db_pool_min, config.db_pool_max)
    await storage.connect()
    try:
        tracker = JobTracker(storage.pool, "github")
        job_id = await tracker.create_job(
            job_type=IngestJobType.GH_RETRY,
            trigger=IngestTrigger.CLI,
            triggered_by="cli",
            input_params={"status": status_filter, "max_attempts": max_attempts, "count": len(logins)},
        )
        await tracker.mark_running()
        log.info("Job %s started (%d retries)", job_id, len(logins))

        async with GitHubClient(config, pool) as client:
            orch = GHOrchestrator(config, client, storage, job_tracker=tracker)
            stats = await orch.run(logins)
            await tracker.mark_completed(asdict(stats))
            log.info("Job %s completed", job_id)
            return 0 if stats.failed == 0 else 1
    except Exception as e:
        await tracker.mark_failed(str(e))
        raise
    finally:
        await storage.close()


# ---- HuggingFace commands ----


async def _hf_discover(n: int, alpha: float, output: Path | None) -> int:
    from .common.job_tracker import JobTracker
    from .hf.config import HFConfig
    from .hf.discover import discover_top_authors
    from .hf.storage import HFStorage

    config = HFConfig()
    config.validate()

    storage = HFStorage(config.db_dsn, config.db_pool_min, config.db_pool_max)
    await storage.connect()
    try:
        tracker = JobTracker(storage.pool, "huggingface")
        job_id = await tracker.create_job(
            job_type=IngestJobType.HF_DISCOVER,
            trigger=IngestTrigger.CLI,
            triggered_by="cli",
            input_params={"top": n, "alpha": alpha},
        )
        await tracker.mark_running()
        log.info("Job %s started", job_id)

        ranked = await discover_top_authors(config, n=n, alpha=alpha)
        await tracker.mark_completed({
            "processed": len(ranked),
            "succeeded": len(ranked),
            "failed": 0,
            "skipped": 0,
        })
    except Exception as e:
        await tracker.mark_failed(str(e))
        raise
    finally:
        await storage.close()

    lines = []
    for rank, a in enumerate(ranked, start=1):
        lines.append(
            f"{a.username}\t{rank}\t{a.total_downloads}\t{a.total_likes}\t"
            f"{a.num_models}\t{a.score:.4f}"
        )
    body = "\n".join(lines) + "\n"
    if output:
        output.write_text(body)
        log.info("Wrote %d authors to %s", len(ranked), output)
    else:
        for a in ranked:
            print(a.username)
    log.info("Job %s completed", job_id)
    return 0


async def _hf_ingest(usernames: list[str], concurrency: int | None) -> int:
    from .common.job_tracker import JobTracker
    from .hf.client import HFClient
    from .hf.config import HFConfig
    from .hf.orchestrator import HFOrchestrator
    from .hf.storage import HFStorage

    config = HFConfig()
    config.validate()
    if concurrency:
        config.concurrency = concurrency

    storage = HFStorage(config.db_dsn, config.db_pool_min, config.db_pool_max)
    await storage.connect()
    try:
        tracker = JobTracker(storage.pool, "huggingface")
        job_id = await tracker.create_job(
            job_type=IngestJobType.HF_INGEST,
            trigger=IngestTrigger.CLI,
            triggered_by="cli",
            input_params={"logins": usernames[:100], "total_logins": len(usernames)},
            concurrency=config.concurrency,
        )
        await tracker.mark_running()
        log.info("Job %s started (%d usernames)", job_id, len(usernames))

        async with HFClient(config) as client:
            orch = HFOrchestrator(config, client, storage, job_tracker=tracker)
            stats = await orch.run(usernames)
            await tracker.mark_completed(asdict(stats))
            log.info("Job %s completed", job_id)
            return 0 if stats.failed == 0 else 1
    except Exception as e:
        await tracker.mark_failed(str(e))
        raise
    finally:
        await storage.close()


async def _hf_retry(status_filter: str, max_attempts: int) -> int:
    import asyncpg

    from .common.job_tracker import JobTracker
    from .hf.client import HFClient
    from .hf.config import HFConfig
    from .hf.orchestrator import HFOrchestrator
    from .hf.storage import HFStorage

    config = HFConfig()
    config.validate()

    conn = await asyncpg.connect(config.db_dsn)
    try:
        rows = await conn.fetch(
            "SELECT username FROM hf_checkpoints WHERE status = $1 AND attempt_count < $2",
            status_filter,
            max_attempts,
        )
    finally:
        await conn.close()

    usernames = [r["username"] for r in rows]
    if not usernames:
        log.info("No usernames to retry (status=%s, max_attempts=%d)", status_filter, max_attempts)
        return 0

    log.info("Retrying %d usernames with status=%s", len(usernames), status_filter)
    storage = HFStorage(config.db_dsn, config.db_pool_min, config.db_pool_max)
    await storage.connect()
    try:
        tracker = JobTracker(storage.pool, "huggingface")
        job_id = await tracker.create_job(
            job_type=IngestJobType.HF_RETRY,
            trigger=IngestTrigger.CLI,
            triggered_by="cli",
            input_params={"status": status_filter, "max_attempts": max_attempts, "count": len(usernames)},
        )
        await tracker.mark_running()
        log.info("Job %s started (%d retries)", job_id, len(usernames))

        async with HFClient(config) as client:
            orch = HFOrchestrator(config, client, storage, job_tracker=tracker)
            stats = await orch.run(usernames)
            await tracker.mark_completed(asdict(stats))
            log.info("Job %s completed", job_id)
            return 0 if stats.failed == 0 else 1
    except Exception as e:
        await tracker.mark_failed(str(e))
        raise
    finally:
        await storage.close()


# ---- Status command ----


async def _status() -> int:
    import asyncpg

    from .gh.config import GHConfig

    config = GHConfig()
    conn = await asyncpg.connect(config.db_dsn)
    try:
        # GitHub checkpoints
        gh_rows = await conn.fetch(
            "SELECT status, COUNT(*) as cnt FROM gh_checkpoints GROUP BY status ORDER BY status"
        )
        print("=== GitHub Checkpoints ===")
        for r in gh_rows:
            print(f"  {r['status']}: {r['cnt']}")
        if not gh_rows:
            print("  (no data)")

        # HuggingFace checkpoints
        hf_rows = await conn.fetch(
            "SELECT status, COUNT(*) as cnt FROM hf_checkpoints GROUP BY status ORDER BY status"
        )
        print("\n=== HuggingFace Checkpoints ===")
        for r in hf_rows:
            print(f"  {r['status']}: {r['cnt']}")
        if not hf_rows:
            print("  (no data)")

        # Recent jobs
        job_rows = await conn.fetch(
            "SELECT id, job_type, platform, status, total_items, succeeded_count, "
            "failed_count, skipped_count, created_at "
            "FROM ingest_job WHERE is_deleted = FALSE ORDER BY created_at DESC LIMIT 10"
        )
        print("\n=== Recent Jobs ===")
        for r in job_rows:
            print(
                f"  {r['id']} {r['job_type']} [{r['status']}] "
                f"items={r['total_items']} ok={r['succeeded_count']} "
                f"fail={r['failed_count']} skip={r['skipped_count']}"
            )
        if not job_rows:
            print("  (no jobs)")
    finally:
        await conn.close()
    return 0


# ---- Init schema commands ----


async def _gh_init_schema() -> int:
    from .gh.config import GHConfig
    from .gh.storage import GHStorage

    config = GHConfig()
    schema_path = Path(__file__).parent.parent.parent / "sql" / "gh_schema.sql"
    sql = schema_path.read_text()
    storage = GHStorage(config.db_dsn, config.db_pool_min, config.db_pool_max)
    await storage.connect()
    try:
        await storage.init_schema(sql)
        log.info("GH schema initialized")
    finally:
        await storage.close()
    return 0


async def _hf_init_schema() -> int:
    from .hf.config import HFConfig
    from .hf.storage import HFStorage

    config = HFConfig()
    schema_path = Path(__file__).parent.parent.parent / "sql" / "hf_schema.sql"
    sql = schema_path.read_text()
    storage = HFStorage(config.db_dsn, config.db_pool_min, config.db_pool_max)
    await storage.connect()
    try:
        await storage.init_schema(sql)
        log.info("HF schema initialized")
    finally:
        await storage.close()
    return 0


async def _job_init_schema() -> int:
    import asyncpg

    from .gh.config import GHConfig

    config = GHConfig()
    schema_path = Path(__file__).parent.parent.parent / "sql" / "ingest_job_schema.sql"
    sql = schema_path.read_text()
    conn = await asyncpg.connect(config.db_dsn)
    try:
        await conn.execute(sql)
        log.info("Ingest job schema initialized")
    finally:
        await conn.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="octopod-ingest")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # Init schema
    sub.add_parser("gh-init-schema", help="Create GH tables in Postgres")
    sub.add_parser("hf-init-schema", help="Create HF tables in Postgres")
    sub.add_parser("job-init-schema", help="Create ingest_job tables in Postgres")

    # GH discover
    p = sub.add_parser("gh-discover", help="Discover top-N GitHub users")
    p.add_argument("--top", type=int, default=5000)
    p.add_argument("--alpha", type=float, default=0.5)
    p.add_argument("--output", type=Path)

    # GH ingest
    p = sub.add_parser("gh-ingest", help="Ingest GitHub profiles")
    p.add_argument("--input", type=Path, help="File with logins (one per line or TSV)")
    p.add_argument("--login", action="append", default=[], help="Specific login")
    p.add_argument("--concurrency", type=int)

    # GH retry
    p = sub.add_parser("gh-retry", help="Retry failed GH ingestions")
    p.add_argument("--status", default="failed")
    p.add_argument("--max-attempts", type=int, default=3)

    # HF discover
    p = sub.add_parser("hf-discover", help="Discover top-N HF authors")
    p.add_argument("--top", type=int, default=5000)
    p.add_argument("--alpha", type=float, default=0.5)
    p.add_argument("--output", type=Path)

    # HF ingest
    p = sub.add_parser("hf-ingest", help="Ingest HuggingFace profiles")
    p.add_argument("--input", type=Path, help="File with usernames")
    p.add_argument("--user", action="append", default=[], help="Specific username")
    p.add_argument("--concurrency", type=int)

    # HF retry
    p = sub.add_parser("hf-retry", help="Retry failed HF ingestions")
    p.add_argument("--status", default="failed")
    p.add_argument("--max-attempts", type=int, default=3)

    # Status
    sub.add_parser("status", help="Show checkpoint summary for both platforms")

    args = parser.parse_args()
    _setup_logging()

    if args.cmd == "gh-init-schema":
        return asyncio.run(_gh_init_schema())

    if args.cmd == "hf-init-schema":
        return asyncio.run(_hf_init_schema())

    if args.cmd == "job-init-schema":
        return asyncio.run(_job_init_schema())

    if args.cmd == "gh-discover":
        return asyncio.run(_gh_discover(args.top, args.alpha, args.output))

    if args.cmd == "gh-ingest":
        logins = _load_logins(args.input, args.login)
        if not logins:
            parser.error("no logins provided (use --input or --login)")
        return asyncio.run(_gh_ingest(logins, args.concurrency))

    if args.cmd == "gh-retry":
        return asyncio.run(_gh_retry(args.status, args.max_attempts))

    if args.cmd == "hf-discover":
        return asyncio.run(_hf_discover(args.top, args.alpha, args.output))

    if args.cmd == "hf-ingest":
        usernames = _load_logins(args.input, args.user)
        if not usernames:
            parser.error("no usernames provided (use --input or --user)")
        return asyncio.run(_hf_ingest(usernames, args.concurrency))

    if args.cmd == "hf-retry":
        return asyncio.run(_hf_retry(args.status, args.max_attempts))

    if args.cmd == "status":
        return asyncio.run(_status())

    return 0


if __name__ == "__main__":
    sys.exit(main())
