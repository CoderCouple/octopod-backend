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
    IDENTITY_RESOLVE = "identity_resolve"
    PROFILE_SYNC = "profile_sync"
    EMBED_SYNC = "embed_sync"
    PIPELINE_DAILY = "pipeline_daily"
    PIPELINE_WEEKLY = "pipeline_weekly"
    PIPELINE_SEED = "pipeline_seed"


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
    SCHEDULE = "schedule"


class IngestItemStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    SEED = "seed"
    GH_ONLY = "gh_only"
    HF_ONLY = "hf_only"
    LN_ONLY = "ln_only"
    DEPENDENT = "dependent"


class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ControlSignal(str, Enum):
    NONE = "none"
    PAUSE = "pause"
    CANCEL = "cancel"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
