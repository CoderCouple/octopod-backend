"""
Prometheus metrics with graceful no-op fallback.

All metrics are no-ops if prometheus_client isn't installed. This keeps the
module usable as a plain Python library while giving production observability.
"""
from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server

    _PROM_AVAILABLE = True
except ImportError:
    _PROM_AVAILABLE = False

    class _Noop:
        def labels(self, *a: Any, **kw: Any) -> _Noop:
            return self

        def inc(self, *a: Any, **kw: Any) -> None: ...
        def dec(self, *a: Any, **kw: Any) -> None: ...
        def set(self, *a: Any, **kw: Any) -> None: ...
        def observe(self, *a: Any, **kw: Any) -> None: ...

        def time(self) -> Any:
            class _Ctx:
                def __enter__(self_: Any) -> Any:
                    return self_

                def __exit__(self_: Any, *e: Any) -> bool:
                    return False

            return _Ctx()

    Counter = Gauge = Histogram = lambda *a, **kw: _Noop()  # type: ignore[assignment,misc]

    def start_http_server(*a: Any, **kw: Any) -> None: ...  # type: ignore[misc]


# ---- GitHub metrics ----

users_processed = Counter(
    "ingest_users_processed_total",
    "Users pulled off the work queue",
    ["platform", "status"],
)

github_requests = Counter(
    "ingest_github_requests_total",
    "GitHub API requests",
    ["api", "status"],
)

github_request_seconds = Histogram(
    "ingest_github_request_seconds",
    "Latency of GitHub API requests",
    ["api"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
)

# ---- HuggingFace metrics ----

hf_requests = Counter(
    "ingest_hf_requests_total",
    "HuggingFace API requests",
    ["api", "status"],
)

hf_request_seconds = Histogram(
    "ingest_hf_request_seconds",
    "Latency of HuggingFace API requests",
    ["api"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
)

# ---- Shared metrics ----

db_operations = Counter(
    "ingest_db_operations_total",
    "Database operations",
    ["operation", "status"],
)

db_operation_seconds = Histogram(
    "ingest_db_operation_seconds",
    "Latency of database operations",
    ["operation"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

queue_depth = Gauge(
    "ingest_queue_depth",
    "Depth of the work queue",
    ["platform"],
)

tokens_remaining = Gauge(
    "ingest_tokens_remaining",
    "Remaining rate-limit budget per token",
    ["platform", "token_index"],
)

active_workers = Gauge(
    "ingest_active_workers",
    "Workers currently processing",
    ["platform"],
)


def start_metrics_server(port: int | None = None) -> None:
    if not _PROM_AVAILABLE:
        log.warning("prometheus_client not installed; metrics disabled")
        return
    port = port or int(os.getenv("METRICS_PORT", "9100"))
    try:
        start_http_server(port)
        log.info("Metrics server listening on :%d/metrics", port)
    except OSError as e:
        log.warning("Could not bind metrics server on :%d: %s", port, e)


def is_available() -> bool:
    return _PROM_AVAILABLE
