from pydantic import BaseModel, Field, model_validator


class CreateDeveloperProfileRequest(BaseModel):
    github_username: str | None = Field(default=None, max_length=255)
    linkedin_url: str | None = Field(default=None, max_length=2048)
    huggingface_username: str | None = Field(default=None, max_length=255)
    employee_id: str | None = Field(default=None)
    email_hint: str | None = Field(default=None, max_length=320)
    auto_ingest: bool = True

    @model_validator(mode="after")
    def at_least_one_identifier(self) -> "CreateDeveloperProfileRequest":
        if not any([self.github_username, self.linkedin_url, self.huggingface_username]):
            raise ValueError("At least one platform identifier is required")
        return self


class UpdateDeveloperProfileRequest(BaseModel):
    github_username: str | None = Field(default=None, max_length=255)
    linkedin_url: str | None = Field(default=None, max_length=2048)
    huggingface_username: str | None = Field(default=None, max_length=255)
    employee_id: str | None = Field(default=None)
    email_hint: str | None = Field(default=None, max_length=320)


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    limit: int = Field(default=20, ge=1, le=100)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)
    filters: dict | None = None
    rerank: bool = Field(default=True)


class RankingWeights(BaseModel):
    github_activity: float = 0.20
    technical_influence: float = 0.15
    hiring_fit: float = 0.15
    experience: float = 0.15
    skills_breadth: float = 0.10
    recency: float = 0.10
    oss_contribution: float = 0.10
    hf_impact: float = 0.05

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "RankingWeights":
        total = (
            self.github_activity
            + self.technical_influence
            + self.hiring_fit
            + self.experience
            + self.skills_breadth
            + self.recency
            + self.oss_contribution
            + self.hf_impact
        )
        if abs(total - 1.0) > 0.05:
            raise ValueError(f"Weights must sum to ~1.0, got {total:.4f}")
        return self


class RankProfilesRequest(BaseModel):
    profile_ids: list[str] | None = None
    weights: RankingWeights | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
