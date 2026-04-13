from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


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
    database_url: Optional[str] = None
    postgres_user: str = "octopod"
    postgres_password: str = "octopod"
    postgres_db: str = "octopod_db"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    
    # API Configuration
    api_prefix: str = "/api/v1"
    allowed_origins: list[str] = ["*"]
    
    # Security
    secret_key: str = "your-secret-key-here-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    @property
    def async_database_url(self) -> str:
        if self.database_url:
            return self.database_url.replace("postgresql://", "postgresql+asyncpg://")
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    @property
    def sync_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

settings = Settings()