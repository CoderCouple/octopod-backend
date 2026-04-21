-- Hugging Face ingestion schema.
-- Parallel to gh_* tables; no cross-references.

CREATE TABLE IF NOT EXISTS hf_users (
    username        TEXT PRIMARY KEY,               -- HF's stable identifier
    type            TEXT NOT NULL,                  -- 'user' or 'org'
    fullname        TEXT,
    avatar_url      TEXT,
    is_pro          BOOLEAN,
    num_models      INT NOT NULL DEFAULT 0,
    num_datasets    INT NOT NULL DEFAULT 0,
    num_followers   INT,
    num_following   INT,
    num_likes       INT,
    bio             TEXT,
    website_url     TEXT,
    twitter         TEXT,
    github_username TEXT,                           -- HF exposes linked GitHub account
    linkedin        TEXT,
    created_at      TIMESTAMPTZ,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw             JSONB
);
CREATE INDEX IF NOT EXISTS hf_users_type_idx     ON hf_users (type);
CREATE INDEX IF NOT EXISTS hf_users_ingested_idx ON hf_users (ingested_at DESC);
CREATE INDEX IF NOT EXISTS hf_users_gh_idx       ON hf_users (github_username) WHERE github_username IS NOT NULL;

CREATE TABLE IF NOT EXISTS hf_models (
    id              TEXT PRIMARY KEY,               -- "owner/model-name"
    author          TEXT NOT NULL REFERENCES hf_users(username) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    pipeline_tag    TEXT,
    library_name    TEXT,
    license         TEXT,
    base_model      TEXT,
    downloads_30d   INT NOT NULL DEFAULT 0,
    downloads_all   BIGINT,
    likes           INT NOT NULL DEFAULT 0,
    is_private      BOOLEAN NOT NULL DEFAULT FALSE,
    is_gated        BOOLEAN NOT NULL DEFAULT FALSE,
    is_disabled     BOOLEAN NOT NULL DEFAULT FALSE,
    tags            TEXT[],
    languages       TEXT[],
    datasets_used   TEXT[],
    created_at      TIMESTAMPTZ,
    last_modified   TIMESTAMPTZ,
    sha             TEXT,
    card_data       JSONB,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw             JSONB
);
CREATE INDEX IF NOT EXISTS hf_models_author_idx    ON hf_models (author);
CREATE INDEX IF NOT EXISTS hf_models_pipeline_idx  ON hf_models (pipeline_tag);
CREATE INDEX IF NOT EXISTS hf_models_downloads_idx ON hf_models (downloads_30d DESC);
CREATE INDEX IF NOT EXISTS hf_models_likes_idx     ON hf_models (likes DESC);
CREATE INDEX IF NOT EXISTS hf_models_modified_idx  ON hf_models (last_modified DESC);
CREATE INDEX IF NOT EXISTS hf_models_tags_gin      ON hf_models USING GIN (tags);

CREATE TABLE IF NOT EXISTS hf_datasets (
    id              TEXT PRIMARY KEY,               -- "owner/dataset-name"
    author          TEXT NOT NULL REFERENCES hf_users(username) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    task_categories TEXT[],
    license         TEXT,
    size_category   TEXT,
    downloads_30d   INT NOT NULL DEFAULT 0,
    likes           INT NOT NULL DEFAULT 0,
    is_private      BOOLEAN NOT NULL DEFAULT FALSE,
    is_gated        BOOLEAN NOT NULL DEFAULT FALSE,
    is_disabled     BOOLEAN NOT NULL DEFAULT FALSE,
    tags            TEXT[],
    languages       TEXT[],
    created_at      TIMESTAMPTZ,
    last_modified   TIMESTAMPTZ,
    sha             TEXT,
    card_data       JSONB,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw             JSONB
);
CREATE INDEX IF NOT EXISTS hf_datasets_author_idx    ON hf_datasets (author);
CREATE INDEX IF NOT EXISTS hf_datasets_downloads_idx ON hf_datasets (downloads_30d DESC);
CREATE INDEX IF NOT EXISTS hf_datasets_likes_idx     ON hf_datasets (likes DESC);
CREATE INDEX IF NOT EXISTS hf_datasets_tags_gin      ON hf_datasets USING GIN (tags);

-- Checkpoint table (parallel to gh_checkpoints).
CREATE TABLE IF NOT EXISTS hf_checkpoints (
    username        TEXT PRIMARY KEY,
    status          TEXT NOT NULL DEFAULT 'pending', -- pending | success | failed | skipped
    last_attempt    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_success    TIMESTAMPTZ,
    last_error      TEXT,
    attempt_count   INT NOT NULL DEFAULT 0,
    last_job_id     TEXT                             -- informational link to ingest_job.id
);
CREATE INDEX IF NOT EXISTS hf_checkpoints_status_idx ON hf_checkpoints (status);
