from __future__ import annotations

from dataclasses import dataclass

from app.settings import settings


@dataclass
class BridgeConfig:
    db_dsn: str = ""
    db_pool_min: int = 2
    db_pool_max: int = 10
    concurrency: int = 8
    batch_size: int = 200
    since_hours: int = 24

    def __post_init__(self) -> None:
        if not self.db_dsn:
            self.db_dsn = settings.asyncpg_dsn
        self.db_pool_min = settings.ingest_db_pool_min
        self.db_pool_max = settings.ingest_db_pool_max
        self.concurrency = settings.bridge_concurrency
        self.batch_size = settings.bridge_batch_size
        self.since_hours = settings.bridge_since_hours

    def validate(self) -> None:
        if not self.db_dsn:
            raise ValueError("db_dsn required")
