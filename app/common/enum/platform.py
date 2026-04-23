from enum import Enum


class Platform(str, Enum):
    GITHUB = "github"
    LINKEDIN = "linkedin"
    HUGGINGFACE = "huggingface"
    X_TWITTER = "x_twitter"


class IngestionStatus(str, Enum):
    PENDING = "pending"
    INGESTING = "ingesting"
    COMPLETED = "completed"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"


class FetchStatus(str, Enum):
    PENDING = "pending"
    FETCHING = "fetching"
    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
