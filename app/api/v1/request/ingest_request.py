from typing import Any  # noqa: TC003

from pydantic import BaseModel, Field, model_validator

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


class ManualProfileRequest(BaseModel):
    name: str | None = Field(default=None, description="Display name (metadata only)")
    github_username: str | None = Field(
        default=None, description="GitHub username or profile URL (e.g. 'torvalds' or 'https://github.com/torvalds')"
    )
    huggingface_username: str | None = Field(
        default=None, description="HuggingFace username or profile URL (e.g. 'bigscience' or 'https://huggingface.co/bigscience')"
    )
    linkedin_url: str | None = Field(
        default=None, description="LinkedIn username/slug or full URL (e.g. 'suniltiwari' or 'https://www.linkedin.com/in/suniltiwari/')"
    )

    @model_validator(mode="after")
    def normalize_and_validate(self) -> "ManualProfileRequest":
        # Extract username from GitHub URL
        if self.github_username and "/" in self.github_username:
            parts = self.github_username.rstrip("/").split("/")
            self.github_username = parts[-1]

        # Extract username from HuggingFace URL
        if self.huggingface_username and "/" in self.huggingface_username:
            parts = self.huggingface_username.rstrip("/").split("/")
            self.huggingface_username = parts[-1]

        # Normalize LinkedIn: accept username/slug and build full URL
        if self.linkedin_url and "linkedin.com" not in self.linkedin_url:
            slug = self.linkedin_url.strip("/")
            self.linkedin_url = f"https://www.linkedin.com/in/{slug}/"
        elif self.linkedin_url:
            # Ensure trailing slash for consistency
            self.linkedin_url = self.linkedin_url.rstrip("/") + "/"

        if not any([self.github_username, self.huggingface_username, self.linkedin_url]):
            raise ValueError("At least one platform identifier is required")
        return self


class IdentityResolveRequest(BaseModel):
    since_hours: int = Field(default=24, ge=1, le=8760)
    full_scan: bool = Field(default=False)
