"""GitHub ingestion config — reads from app.settings."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.settings import settings


def _parse_tokens(raw: str) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


@dataclass
class GHConfig:
    github_tokens: list[str] = field(
        default_factory=lambda: _parse_tokens(settings.github_tokens)
    )
    graphql_endpoint: str = field(default_factory=lambda: settings.gh_graphql_endpoint)
    rest_endpoint: str = field(default_factory=lambda: settings.gh_rest_endpoint)
    db_dsn: str = field(default_factory=lambda: settings.asyncpg_dsn)
    db_pool_min: int = field(default_factory=lambda: settings.ingest_db_pool_min)
    db_pool_max: int = field(default_factory=lambda: settings.ingest_db_pool_max)
    concurrency: int = field(default_factory=lambda: settings.gh_concurrency)
    max_repos_per_user: int = field(default_factory=lambda: settings.gh_max_repos_per_user)
    max_commits_per_repo: int = field(default_factory=lambda: settings.gh_max_commits_per_repo)
    max_events_per_user: int = field(default_factory=lambda: settings.gh_max_events_per_user)
    skip_forks: bool = field(default_factory=lambda: settings.gh_skip_forks)
    refresh_after_hours: int = field(default_factory=lambda: settings.gh_refresh_after_hours)
    max_retries: int = field(default_factory=lambda: settings.gh_max_retries)
    base_backoff_seconds: float = field(default_factory=lambda: settings.gh_base_backoff)
    request_timeout: float = field(default_factory=lambda: settings.gh_request_timeout)

    def validate(self) -> None:
        if not self.github_tokens:
            raise ValueError(
                "No GitHub tokens configured. Set GITHUB_TOKENS env var "
                "(comma-separated personal access tokens)."
            )
        if self.concurrency < 1:
            raise ValueError("gh_concurrency must be >= 1")


gh_config = GHConfig()
