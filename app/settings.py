
import platform

from pydantic_settings import BaseSettings, SettingsConfigDict


def _detect_env_file() -> str:
    """Load .env.local on macOS (dev laptop), .env.dev on Linux (AWS ECS)."""
    return ".env.local" if platform.system() == "Darwin" else ".env.dev"


class Settings(BaseSettings):
    app_name: str = "Octopod Backend"
    app_desc: str = "Crowdsourced Org Graph System"
    app_version: str = "0.0.1"
    debug: bool = False
    environment: str = "development"

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000

    # Database Configuration
    database_url: str | None = None
    postgres_user: str = "octopod"
    postgres_password: str = "octopod"
    postgres_db: str = "octopod_db"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # API Configuration
    api_prefix: str = "/api/v1"
    allowed_origins: list[str] = ["*"]

    # External API Keys
    github_token: str | None = None
    proxycurl_api_key: str | None = None
    huggingface_token: str | None = None

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_grpc_port: int = 6334
    qdrant_url: str | None = None  # Qdrant Cloud URL (overrides host/port when set)
    qdrant_api_key: str | None = None  # Qdrant Cloud API key

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_provider: str = "sentence_transformer"
    embedding_dimension: int = 384

    # Reranker
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_enabled: bool = True

    # GitHub Ingestion
    github_tokens: str = ""  # Comma-separated PATs for token rotation
    gh_graphql_endpoint: str = "https://api.github.com/graphql"
    gh_rest_endpoint: str = "https://api.github.com"
    gh_concurrency: int = 8
    gh_max_repos_per_user: int = 10
    gh_max_commits_per_repo: int = 10
    gh_max_events_per_user: int = 100
    gh_skip_forks: bool = True
    gh_refresh_after_hours: int = 24
    gh_max_retries: int = 5
    gh_base_backoff: float = 2.0
    gh_request_timeout: float = 30.0

    # HuggingFace Ingestion
    huggingface_tokens: str = ""  # Comma-separated tokens
    hf_endpoint: str = "https://huggingface.co"
    hf_concurrency: int = 8
    hf_max_models_per_user: int = 500
    hf_max_datasets_per_user: int = 500
    hf_refresh_after_hours: int = 24
    hf_max_retries: int = 5
    hf_base_backoff: float = 2.0
    hf_request_timeout: float = 30.0

    # Ingestion DB pool (asyncpg direct connection for bulk ingestion)
    ingest_db_pool_min: int = 2
    ingest_db_pool_max: int = 10

    # LinkedIn Ingestion (Proxycurl)
    ln_concurrency: int = 4
    ln_rate_limit_rpm: int = 300
    ln_daily_budget_usd: float = 50.0
    ln_cost_per_profile: float = 0.01
    ln_max_retries: int = 3
    ln_request_timeout: float = 30.0

    # Bridge / Profile Sync
    bridge_concurrency: int = 8
    bridge_batch_size: int = 200
    bridge_since_hours: int = 24

    # OpenSearch
    opensearch_host: str = "localhost"
    opensearch_port: int = 9200
    opensearch_use_ssl: bool = False
    opensearch_enabled: bool = False
    opensearch_index: str = "octopod_profiles"
    opensearch_username: str | None = None
    opensearch_password: str | None = None

    # AWS Cognito
    cognito_user_pool_id: str = ""
    cognito_region: str = "us-west-2"
    cognito_app_client_id: str = ""

    # Security (legacy — kept for backward compat)
    secret_key: str = "your-secret-key-here-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # OAuth - Gmail
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""

    # OAuth - Outlook
    ms_client_id: str = ""
    ms_client_secret: str = ""
    ms_tenant_id: str = ""
    ms_redirect_uri: str = ""

    # SendGrid
    sendgrid_api_key: str = ""
    sendgrid_webhook_secret: str = ""

    # Email Enrichment
    hunter_api_key: str = ""
    apollo_api_key: str = ""

    # Email Sending Engine
    tracking_base_url: str = "http://localhost:8000"
    send_worker_poll_interval: int = 30
    send_worker_batch_size: int = 50
    default_daily_send_limit: int = 35
    reply_check_interval: int = 300
    token_encryption_key: str = ""

    @property
    def cognito_jwks_url(self) -> str:
        return (
            f"https://cognito-idp.{self.cognito_region}.amazonaws.com"
            f"/{self.cognito_user_pool_id}/.well-known/jwks.json"
        )

    @property
    def cognito_issuer(self) -> str:
        return (
            f"https://cognito-idp.{self.cognito_region}.amazonaws.com"
            f"/{self.cognito_user_pool_id}"
        )

    model_config = SettingsConfigDict(
        env_file=_detect_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def async_database_url(self) -> str:
        if self.database_url:
            return self.database_url.replace("postgresql://", "postgresql+asyncpg://")
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def asyncpg_dsn(self) -> str:
        """Direct asyncpg DSN for bulk ingestion (no SQLAlchemy prefix)."""
        if self.database_url:
            return self.database_url.replace("postgresql+asyncpg://", "postgresql://")
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        if self.database_url:
            return self.database_url.replace("postgresql://", "postgresql+psycopg://")
        return f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

settings = Settings()
