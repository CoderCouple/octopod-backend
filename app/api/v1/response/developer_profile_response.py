from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class DeveloperProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    github_username: str | None = None
    huggingface_username: str | None = None
    email_hint: str | None = None
    ingestion_status: str
    last_ingested_at: datetime | None = None
    # Merged dev data
    display_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    company: str | None = None
    location: str | None = None
    website: str | None = None
    total_repos: int | None = 0
    total_stars: int | None = 0
    total_contributions: int | None = 0
    total_followers: int | None = 0
    total_hf_models: int | None = 0
    total_hf_datasets: int | None = 0
    total_hf_spaces: int | None = 0
    total_hf_downloads: int | None = 0
    total_papers: int | None = 0
    languages: list[str] | None = None
    skills: list[str] | None = None
    topics: list[str] | None = None
    dev_merged_at: datetime | None = None
    # Audit
    is_deleted: bool
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime


class CohesiveProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    developer_profile_id: str
    display_name: str | None = None
    bio: str | None = None
    headline: str | None = None
    location: str | None = None
    avatar_url: str | None = None
    company: str | None = None
    website: str | None = None
    total_repos: int | None = 0
    total_stars: int | None = 0
    total_contributions: int | None = 0
    total_followers: int | None = 0
    total_hf_models: int | None = 0
    total_hf_datasets: int | None = 0
    total_hf_spaces: int | None = 0
    total_hf_downloads: int | None = 0
    total_papers: int | None = 0
    languages: list[str] | None = None
    skills: list[str] | None = None
    topics: list[str] | None = None
    years_of_experience: int | None = None
    current_title: str | None = None
    current_company: str | None = None
    job_history: list[dict[str, Any]] | None = None
    source_priority: dict[str, str] | None = None
    merged_at: datetime | None = None


class ProfileRankingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    cohesive_individual_profile_id: str
    github_activity_score: float | None = 0
    technical_influence_score: float | None = 0
    hiring_fit_score: float | None = 0
    experience_score: float | None = 0
    skills_breadth_score: float | None = 0
    recency_score: float | None = 0
    oss_contribution_score: float | None = 0
    hf_impact_score: float | None = 0
    composite_score: float | None = 0
    weight_config: dict[str, float] | None = None
    computed_at: datetime | None = None


class IngestionStatusResponse(BaseModel):
    developer_profile_id: str
    ingestion_status: str
    last_ingested_at: datetime | None = None


class SearchResultResponse(BaseModel):
    profile: CohesiveProfileResponse
    score: float
    ranking: ProfileRankingResponse | None = None
