-- GitHub Ingestion Schema
-- Designed for idempotent upserts and efficient querying.

CREATE TABLE IF NOT EXISTS gh_users (
    id              BIGINT PRIMARY KEY,             -- GitHub numeric ID (stable across renames)
    login           TEXT NOT NULL UNIQUE,           -- username (may change)
    name            TEXT,
    email           TEXT,
    bio             TEXT,
    company         TEXT,
    location        TEXT,
    website_url     TEXT,
    twitter         TEXT,
    avatar_url      TEXT,
    followers       INT NOT NULL DEFAULT 0,
    following       INT NOT NULL DEFAULT 0,
    public_repos    INT NOT NULL DEFAULT 0,
    is_hireable     BOOLEAN,
    created_at      TIMESTAMPTZ,
    updated_at_gh   TIMESTAMPTZ,                    -- GitHub's updatedAt
    social_accounts       JSONB,                      -- [{provider, url, displayName}]
    contribution_stats    JSONB,                      -- {totalCommit, totalPR, totalIssue, totalRepo}
    contribution_calendar JSONB,                      -- {totalContributions, weeks: [...]}
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw             JSONB                           -- full payload for re-processing
);
CREATE INDEX IF NOT EXISTS gh_users_login_idx      ON gh_users (login);
CREATE INDEX IF NOT EXISTS gh_users_ingested_idx   ON gh_users (ingested_at DESC);

CREATE TABLE IF NOT EXISTS gh_repositories (
    id              BIGINT PRIMARY KEY,
    owner_id        BIGINT NOT NULL REFERENCES gh_users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    full_name       TEXT NOT NULL UNIQUE,           -- owner/name
    description     TEXT,
    primary_language TEXT,
    is_fork         BOOLEAN NOT NULL DEFAULT FALSE,
    is_archived     BOOLEAN NOT NULL DEFAULT FALSE,
    stars           INT NOT NULL DEFAULT 0,
    forks           INT NOT NULL DEFAULT 0,
    watchers        INT NOT NULL DEFAULT 0,
    open_issues     INT NOT NULL DEFAULT 0,
    size_kb         INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ,
    updated_at_gh   TIMESTAMPTZ,
    pushed_at       TIMESTAMPTZ,
    topics          TEXT[],
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw             JSONB
);
CREATE INDEX IF NOT EXISTS gh_repos_owner_idx      ON gh_repositories (owner_id);
CREATE INDEX IF NOT EXISTS gh_repos_language_idx   ON gh_repositories (primary_language);
CREATE INDEX IF NOT EXISTS gh_repos_stars_idx      ON gh_repositories (stars DESC);
CREATE INDEX IF NOT EXISTS gh_repos_pushed_idx     ON gh_repositories (pushed_at DESC);

CREATE TABLE IF NOT EXISTS gh_commits (
    oid             TEXT NOT NULL,                  -- commit SHA
    repo_id         BIGINT NOT NULL REFERENCES gh_repositories(id) ON DELETE CASCADE,
    author_id       BIGINT,                          -- nullable; no FK — commit authors may not be ingested users
    author_login    TEXT,
    author_email    TEXT,
    message         TEXT,
    committed_at    TIMESTAMPTZ,
    additions       INT,
    deletions       INT,
    changed_files   INT,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (oid, repo_id)
);
CREATE INDEX IF NOT EXISTS gh_commits_author_idx   ON gh_commits (author_id);
CREATE INDEX IF NOT EXISTS gh_commits_date_idx     ON gh_commits (committed_at DESC);

CREATE TABLE IF NOT EXISTS gh_activity_events (
    id              TEXT PRIMARY KEY,               -- GitHub event ID
    user_id         BIGINT NOT NULL REFERENCES gh_users(id) ON DELETE CASCADE,
    type            TEXT NOT NULL,                  -- PushEvent, PullRequestEvent, etc.
    repo_name       TEXT,
    payload         JSONB,
    created_at      TIMESTAMPTZ NOT NULL,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS gh_events_user_idx      ON gh_activity_events (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS gh_events_type_idx      ON gh_activity_events (type);

-- Checkpoint table: resume interrupted runs and skip recently-ingested profiles.
CREATE TABLE IF NOT EXISTS gh_checkpoints (
    login           TEXT PRIMARY KEY,
    status          TEXT NOT NULL DEFAULT 'pending', -- pending | success | failed | skipped
    last_attempt    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_success    TIMESTAMPTZ,
    last_error      TEXT,
    attempt_count   INT NOT NULL DEFAULT 0,
    last_job_id     TEXT                             -- informational link to ingest_job.id
);
CREATE INDEX IF NOT EXISTS gh_checkpoints_status_idx ON gh_checkpoints (status);
