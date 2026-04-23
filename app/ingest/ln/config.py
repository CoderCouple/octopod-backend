from __future__ import annotations

from dataclasses import dataclass

from app.settings import settings


@dataclass
class LNConfig:
    api_key: str = ""
    db_dsn: str = ""
    db_pool_min: int = 2
    db_pool_max: int = 10
    concurrency: int = 4
    rate_limit_rpm: int = 300
    daily_budget_usd: float = 50.0
    cost_per_profile: float = 0.01
    max_retries: int = 3
    request_timeout: float = 30.0

    def __post_init__(self) -> None:
        if not self.api_key:
            self.api_key = settings.proxycurl_api_key or ""
        if not self.db_dsn:
            self.db_dsn = settings.asyncpg_dsn
        self.db_pool_min = settings.ingest_db_pool_min
        self.db_pool_max = settings.ingest_db_pool_max
        self.concurrency = settings.ln_concurrency
        self.rate_limit_rpm = settings.ln_rate_limit_rpm
        self.daily_budget_usd = settings.ln_daily_budget_usd
        self.cost_per_profile = settings.ln_cost_per_profile
        self.max_retries = settings.ln_max_retries
        self.request_timeout = settings.ln_request_timeout

    def validate(self) -> None:
        if not self.api_key:
            raise ValueError("Proxycurl API key is required (set PROXYCURL_API_KEY)")
        if not self.db_dsn:
            raise ValueError("db_dsn required")
