"""HuggingFace ingestion config — reads from app.settings."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.settings import settings


def _parse_tokens(raw: str) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


@dataclass
class HFConfig:
    hf_tokens: list[str] = field(
        default_factory=lambda: _parse_tokens(settings.hf_tokens)
    )
    endpoint: str = field(default_factory=lambda: settings.hf_endpoint)
    db_dsn: str = field(default_factory=lambda: settings.asyncpg_dsn)
    db_pool_min: int = field(default_factory=lambda: settings.ingest_db_pool_min)
    db_pool_max: int = field(default_factory=lambda: settings.ingest_db_pool_max)
    concurrency: int = field(default_factory=lambda: settings.hf_concurrency)
    max_models_per_user: int = field(default_factory=lambda: settings.hf_max_models_per_user)
    max_datasets_per_user: int = field(default_factory=lambda: settings.hf_max_datasets_per_user)
    refresh_after_hours: int = field(default_factory=lambda: settings.hf_refresh_after_hours)
    max_retries: int = field(default_factory=lambda: settings.hf_max_retries)
    base_backoff_seconds: float = field(default_factory=lambda: settings.hf_base_backoff)
    request_timeout: float = field(default_factory=lambda: settings.hf_request_timeout)

    def validate(self) -> None:
        if self.concurrency < 1:
            raise ValueError("hf_concurrency must be >= 1")


hf_config = HFConfig()
