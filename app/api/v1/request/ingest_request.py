from typing import Any  # noqa: TC003

from pydantic import BaseModel, Field

# ---- Source (GH/HF/LN) ----


class DiscoverRequest(BaseModel):
    top: int = Field(default=5000, ge=1, le=50000)
    alpha: float = Field(default=0.5, ge=0.0, le=1.0)


class GHDiscoverRequest(BaseModel):
    top: int = Field(default=5000, ge=1, le=50000)
    alpha: float = Field(default=0.5, ge=0.0, le=1.0)
    org: str | None = Field(default=None, description="GitHub org/company to scope search (e.g. 'google', 'microsoft')")
    languages: list[str] | None = Field(default=None, description="Filter by programming language (e.g. ['python', 'rust'])")
    topics: list[str] | None = Field(default=None, description="Filter by GitHub repo topic (e.g. ['machine-learning'])")
    min_followers: int | None = Field(default=None, ge=1, description="Minimum follower count")
    min_repos: int | None = Field(default=None, ge=1, description="Minimum number of public repos")


class HFDiscoverRequest(BaseModel):
    top: int = Field(default=5000, ge=1, le=50000)
    alpha: float = Field(default=0.5, ge=0.0, le=1.0)
    pipeline_tag: str | None = Field(default=None, description="Filter by HF pipeline tag (e.g. 'text-generation', 'image-classification')")
    library: str | None = Field(default=None, description="Filter by ML library (e.g. 'transformers', 'diffusers')")


class IngestRequest(BaseModel):
    logins: list[str] = Field(default_factory=list, min_length=1)
    concurrency: int | None = Field(default=None, ge=1, le=64)


class GHFilterRequest(BaseModel):
    min_commits: int = Field(default=1, ge=1, description="Minimum commits in the lookback window")
    days: int = Field(default=90, ge=1, le=365, description="Lookback window in days")
    min_followers: int | None = Field(default=None, ge=0, description="Minimum follower count")
    min_stars: int | None = Field(default=None, ge=0, description="Minimum total stars across all repos")
    min_repos: int | None = Field(default=None, ge=1, description="Minimum number of public repos")
    languages: list[str] | None = Field(default=None, description="Must have at least one repo in these languages")
    company: str | None = Field(default=None, description="Company substring match (case-insensitive)")
    location: str | None = Field(default=None, description="Location substring match (case-insensitive)")
    limit: int = Field(default=500, ge=1, le=5000, description="Max results to return")


class LNIngestRequest(BaseModel):
    max_profiles: int = Field(default=5000, ge=1, le=50000)
    concurrency: int | None = Field(default=None, ge=1, le=16)


# ---- Job ----


class RetryRequest(BaseModel):
    status: str = Field(default="failed")
    max_attempts: int = Field(default=3, ge=1, le=10)


# ---- Pipeline ----


class SyncRequest(BaseModel):
    platform: str = Field(default="all", description="all|gh_only|hf_only|ln_only")
    since_hours: int = Field(default=24, ge=1, le=720)


class EmbedRequest(BaseModel):
    batch_size: int = Field(default=200, ge=1, le=1000)
    include_opensearch: bool = Field(default=False)


class PipelineStartRequest(BaseModel):
    pipeline_type: str = Field(description="Pipeline type: daily, weekly, seed, gh_only, hf_only, ln_only, dependent")
    input_params: dict[str, Any] = Field(default_factory=dict)


# ---- Schedule ----


class ScheduleCreateRequest(BaseModel):
    name: str = Field(max_length=100)
    pipeline_type: str = Field(description="Pipeline type to schedule")
    input_params: dict[str, Any] = Field(default_factory=dict)
    cron_expression: str = Field(description="Cron expression (e.g. '0 2 * * *')")
    is_enabled: bool = Field(default=True)


class ScheduleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    pipeline_type: str | None = None
    input_params: dict[str, Any] | None = None
    cron_expression: str | None = None
    is_enabled: bool | None = None


# ---- Identity ----


class IdentityResolveRequest(BaseModel):
    since_hours: int = Field(default=24, ge=1, le=8760)
    full_scan: bool = Field(default=False)
