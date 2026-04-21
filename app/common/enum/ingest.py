from enum import Enum


class IngestJobType(str, Enum):
    GH_DISCOVER = "gh_discover"
    GH_INGEST = "gh_ingest"
    GH_RETRY = "gh_retry"
    HF_DISCOVER = "hf_discover"
    HF_INGEST = "hf_ingest"
    HF_RETRY = "hf_retry"


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
