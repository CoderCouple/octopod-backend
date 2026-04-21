-- Persistent job tracking for ingestion engine.
-- Forward-compatible with future workflow execution system
-- (workflow_execution -> execution_phase -> execution_log).

CREATE TABLE IF NOT EXISTS ingest_job (
    id                  TEXT PRIMARY KEY DEFAULT 'ij_' || gen_random_uuid(),
    job_type            VARCHAR(30) NOT NULL,       -- gh_discover|gh_ingest|gh_retry|hf_discover|hf_ingest|hf_retry
    platform            VARCHAR(30) NOT NULL,       -- github|huggingface
    status              VARCHAR(30) NOT NULL DEFAULT 'pending',  -- pending|running|completed|failed|cancelled
    trigger             VARCHAR(30) NOT NULL DEFAULT 'api',      -- api|cli|cron|workflow
    triggered_by        TEXT,                        -- user_id or 'system'
    execution_phase_id  TEXT,                        -- nullable FK -> future execution_phase.id
    input_params        JSONB DEFAULT '{}'::jsonb,   -- {logins, top, alpha, concurrency, ...}
    concurrency         INTEGER,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    duration_ms         INTEGER,
    total_items         INTEGER DEFAULT 0,
    succeeded_count     INTEGER DEFAULT 0,
    failed_count        INTEGER DEFAULT 0,
    skipped_count       INTEGER DEFAULT 0,
    error_summary       TEXT,
    error_detail        JSONB,
    stats               JSONB DEFAULT '{}'::jsonb,   -- full IngestStats snapshot
    is_deleted          BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at          TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS ingest_job_status_idx     ON ingest_job (status);
CREATE INDEX IF NOT EXISTS ingest_job_type_idx       ON ingest_job (job_type);
CREATE INDEX IF NOT EXISTS ingest_job_platform_idx   ON ingest_job (platform);
CREATE INDEX IF NOT EXISTS ingest_job_started_idx    ON ingest_job (started_at DESC);
CREATE INDEX IF NOT EXISTS ingest_job_phase_idx      ON ingest_job (execution_phase_id)
    WHERE execution_phase_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS ingest_job_item (
    id              TEXT PRIMARY KEY DEFAULT 'iji_' || gen_random_uuid(),
    job_id          TEXT NOT NULL REFERENCES ingest_job(id) ON DELETE CASCADE,
    login           TEXT NOT NULL,              -- gh login or hf username
    platform        VARCHAR(30) NOT NULL,
    status          VARCHAR(30) NOT NULL DEFAULT 'pending',  -- pending|running|success|failed|skipped
    attempt_number  INTEGER NOT NULL DEFAULT 1,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    duration_ms     INTEGER,
    records_written JSONB DEFAULT '{}'::jsonb,  -- {repos: 8, commits: 50, events: 100} or {models: 5, datasets: 3}
    error_type      VARCHAR(30),               -- permanent|transient|null
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at      TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS ingest_job_item_job_idx    ON ingest_job_item (job_id);
CREATE INDEX IF NOT EXISTS ingest_job_item_login_idx  ON ingest_job_item (login);
CREATE INDEX IF NOT EXISTS ingest_job_item_status_idx ON ingest_job_item (status);
CREATE INDEX IF NOT EXISTS ingest_job_item_combo_idx  ON ingest_job_item (job_id, status);

-- Add last_job_id to existing checkpoint tables (idempotent for existing DBs).
ALTER TABLE gh_checkpoints ADD COLUMN IF NOT EXISTS last_job_id TEXT;
ALTER TABLE hf_checkpoints ADD COLUMN IF NOT EXISTS last_job_id TEXT;

-- Add contribution/social columns to gh_users (idempotent for existing DBs).
ALTER TABLE gh_users ADD COLUMN IF NOT EXISTS social_accounts JSONB;
ALTER TABLE gh_users ADD COLUMN IF NOT EXISTS contribution_stats JSONB;
ALTER TABLE gh_users ADD COLUMN IF NOT EXISTS contribution_calendar JSONB;
