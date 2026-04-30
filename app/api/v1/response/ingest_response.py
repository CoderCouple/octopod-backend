from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

# ---- Shared ----


class JobStartedResponse(BaseModel):
    job_id: str
    status: str = "started"


# ---- Source ----


class GHFilteredUser(BaseModel):
    login: str
    followers: int
    public_repos: int
    company: str | None = None
    location: str | None = None
    total_stars: int
    languages: list[str]
    commit_count: int


class GHFilterResponse(BaseModel):
    total: int
    logins: list[str]
    users: list[GHFilteredUser]


class RetryStartedResponse(BaseModel):
    gh_job_id: str
    hf_job_id: str
    status: str = "started"


# ---- Job ----


class CheckpointCounts(BaseModel):
    github: dict[str, int]
    huggingface: dict[str, int]


class IngestStatusResponse(BaseModel):
    github: dict[str, int]
    huggingface: dict[str, int]
    recent_jobs: list[dict[str, Any]]


class JobSummary(BaseModel):
    id: str
    job_type: str
    platform: str
    status: str
    trigger: str | None = None
    triggered_by: str | None = None
    execution_phase_id: str | None = None
    input_params: Any | None = None
    concurrency: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    total_items: int | None = None
    succeeded_count: int | None = None
    failed_count: int | None = None
    skipped_count: int | None = None
    error_summary: str | None = None
    error_detail: str | None = None
    stats: Any | None = None
    is_deleted: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class JobDetail(JobSummary):
    item_counts: dict[str, int] = {}


class JobItem(BaseModel):
    id: str
    job_id: str
    login: str
    platform: str
    status: str
    attempt_number: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    records_written: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---- Pipeline ----


class PipelineStartedResponse(BaseModel):
    pipeline_type: str
    status: str = "started"


class PipelineControlResponse(BaseModel):
    execution_id: str
    control_signal: str


class PipelineResumeResponse(BaseModel):
    execution_id: str
    status: str
    from_step: int | None = None


class PipelineRerunResponse(BaseModel):
    pipeline_type: str
    status: str = "started"
    rerun_of: str


class PipelineHealthResponse(BaseModel):
    checkpoints: dict[str, dict[str, int]]
    latest_jobs: list[dict[str, Any]]
    profile_counts: dict[str, int]


# ---- Schedule ----


class ScheduleResponse(BaseModel):
    id: str
    name: str
    pipeline_type: str
    cron_expression: str
    is_enabled: bool
    next_run_at: str | None = None
    input_params: Any | None = None
    last_run_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ScheduleDeleteResponse(BaseModel):
    id: str
    deleted: bool = True


# ---- Identity ----


class ProfilePreview(BaseModel):
    id: str
    github_username: str | None = None
    huggingface_username: str | None = None
    email_hint: str | None = None
    display_name: str | None = None
    company: str | None = None
    location: str | None = None
    avatar_url: str | None = None
    website: str | None = None
    total_repos: int | None = None
    total_stars: int | None = None
    total_hf_models: int | None = None
    total_hf_downloads: int | None = None


class MergeCandidateSummary(BaseModel):
    id: str
    source_profile_id: str
    target_profile_id: str
    confidence_score: float
    signals: Any | None = None
    status: str
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    merged_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    source_name: str | None = None
    source_gh: str | None = None
    source_hf: str | None = None
    target_name: str | None = None
    target_gh: str | None = None
    target_hf: str | None = None


class MergeCandidateDetail(BaseModel):
    id: str
    source_profile_id: str
    target_profile_id: str
    confidence_score: float
    signals: Any | None = None
    status: str
    resolved_profile_id: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    merged_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    source_profile: ProfilePreview | None = None
    target_profile: ProfilePreview | None = None


class MergeApproveResponse(BaseModel):
    id: str
    status: str = "merged"
    source_profile_id: str
    target_profile_id: str


class MergeRejectResponse(BaseModel):
    id: str
    status: str = "rejected"


class IdentityStatusCount(BaseModel):
    status: str
    count: int
    avg_score: float = 0


class IdentityStatsResponse(BaseModel):
    by_status: list[IdentityStatusCount]
    total_merged_profiles: int = 0
