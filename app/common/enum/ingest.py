from enum import Enum


class IngestJobType(str, Enum):
    GH_DISCOVER = "gh_discover"
    GH_INGEST = "gh_ingest"
    GH_RETRY = "gh_retry"
    HF_DISCOVER = "hf_discover"
    HF_INGEST = "hf_ingest"
    HF_RETRY = "hf_retry"
    LN_DISCOVER = "ln_discover"
    LN_INGEST = "ln_ingest"
    LN_RETRY = "ln_retry"
    PROFILE_SYNC = "profile_sync"
    EMBED_SYNC = "embed_sync"
    PIPELINE_DAILY = "pipeline_daily"
    PIPELINE_WEEKLY = "pipeline_weekly"


class IngestJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IngestTrigger(str, Enum):
    API = "api"
    CLI = "cli"
    CRON = "cron"
    WORKFLOW = "workflow"


class IngestItemStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
