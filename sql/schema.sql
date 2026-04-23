-- ============================================================
-- Octopod Backend - Consolidated Database Schema
-- All tables for a fresh database deployment.
-- Run once: psql -f sql/schema.sql
-- ============================================================


-- ************************************************************
-- SECTION 1: GITHUB INGESTION (Layer 1 - Raw Data)
-- ************************************************************

CREATE TABLE IF NOT EXISTS gh_users (
    id                    BIGINT PRIMARY KEY,
    login                 TEXT NOT NULL UNIQUE,
    name                  TEXT,
    email                 TEXT,
    bio                   TEXT,
    company               TEXT,
    location              TEXT,
    website_url           TEXT,
    twitter               TEXT,
    avatar_url            TEXT,
    followers             INT NOT NULL DEFAULT 0,
    following             INT NOT NULL DEFAULT 0,
    public_repos          INT NOT NULL DEFAULT 0,
    is_hireable           BOOLEAN,
    created_at            TIMESTAMPTZ,
    updated_at_gh         TIMESTAMPTZ,
    social_accounts       JSONB,
    contribution_stats    JSONB,
    contribution_calendar JSONB,
    ingested_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw                   JSONB
);

CREATE INDEX IF NOT EXISTS gh_users_login_idx    ON gh_users (login);
CREATE INDEX IF NOT EXISTS gh_users_ingested_idx ON gh_users (ingested_at DESC);

CREATE TABLE IF NOT EXISTS gh_repositories (
    id               BIGINT PRIMARY KEY,
    owner_id         BIGINT NOT NULL REFERENCES gh_users(id) ON DELETE CASCADE,
    name             TEXT NOT NULL,
    full_name        TEXT NOT NULL UNIQUE,
    description      TEXT,
    primary_language TEXT,
    is_fork          BOOLEAN NOT NULL DEFAULT FALSE,
    is_archived      BOOLEAN NOT NULL DEFAULT FALSE,
    stars            INT NOT NULL DEFAULT 0,
    forks            INT NOT NULL DEFAULT 0,
    watchers         INT NOT NULL DEFAULT 0,
    open_issues      INT NOT NULL DEFAULT 0,
    size_kb          INT NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ,
    updated_at_gh    TIMESTAMPTZ,
    pushed_at        TIMESTAMPTZ,
    topics           TEXT[],
    ingested_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw              JSONB
);

CREATE INDEX IF NOT EXISTS gh_repos_owner_idx    ON gh_repositories (owner_id);
CREATE INDEX IF NOT EXISTS gh_repos_language_idx ON gh_repositories (primary_language);
CREATE INDEX IF NOT EXISTS gh_repos_stars_idx    ON gh_repositories (stars DESC);
CREATE INDEX IF NOT EXISTS gh_repos_pushed_idx   ON gh_repositories (pushed_at DESC);

CREATE TABLE IF NOT EXISTS gh_commits (
    oid           TEXT NOT NULL,
    repo_id       BIGINT NOT NULL REFERENCES gh_repositories(id) ON DELETE CASCADE,
    author_id     BIGINT,
    author_login  TEXT,
    author_email  TEXT,
    message       TEXT,
    committed_at  TIMESTAMPTZ,
    additions     INT,
    deletions     INT,
    changed_files INT,
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (oid, repo_id)
);

CREATE INDEX IF NOT EXISTS gh_commits_author_idx ON gh_commits (author_id);
CREATE INDEX IF NOT EXISTS gh_commits_date_idx   ON gh_commits (committed_at DESC);

CREATE TABLE IF NOT EXISTS gh_activity_events (
    id          TEXT PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES gh_users(id) ON DELETE CASCADE,
    type        TEXT NOT NULL,
    repo_name   TEXT,
    payload     JSONB,
    created_at  TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS gh_events_user_idx ON gh_activity_events (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS gh_events_type_idx ON gh_activity_events (type);

CREATE TABLE IF NOT EXISTS gh_checkpoints (
    login         TEXT PRIMARY KEY,
    status        TEXT NOT NULL DEFAULT 'pending',
    last_attempt  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_success  TIMESTAMPTZ,
    last_error    TEXT,
    attempt_count INT NOT NULL DEFAULT 0,
    last_job_id   TEXT
);

CREATE INDEX IF NOT EXISTS gh_checkpoints_status_idx ON gh_checkpoints (status);


-- ************************************************************
-- SECTION 2: HUGGINGFACE INGESTION (Layer 1 - Raw Data)
-- ************************************************************

CREATE TABLE IF NOT EXISTS hf_users (
    username        TEXT PRIMARY KEY,
    type            TEXT NOT NULL,
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
    github_username TEXT,
    linkedin        TEXT,
    created_at      TIMESTAMPTZ,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw             JSONB
);

CREATE INDEX IF NOT EXISTS hf_users_type_idx     ON hf_users (type);
CREATE INDEX IF NOT EXISTS hf_users_ingested_idx ON hf_users (ingested_at DESC);
CREATE INDEX IF NOT EXISTS hf_users_gh_idx       ON hf_users (github_username) WHERE github_username IS NOT NULL;

CREATE TABLE IF NOT EXISTS hf_models (
    id            TEXT PRIMARY KEY,
    author        TEXT NOT NULL REFERENCES hf_users(username) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    pipeline_tag  TEXT,
    library_name  TEXT,
    license       TEXT,
    base_model    TEXT,
    downloads_30d INT NOT NULL DEFAULT 0,
    downloads_all BIGINT,
    likes         INT NOT NULL DEFAULT 0,
    is_private    BOOLEAN NOT NULL DEFAULT FALSE,
    is_gated      BOOLEAN NOT NULL DEFAULT FALSE,
    is_disabled   BOOLEAN NOT NULL DEFAULT FALSE,
    tags          TEXT[],
    languages     TEXT[],
    datasets_used TEXT[],
    created_at    TIMESTAMPTZ,
    last_modified TIMESTAMPTZ,
    sha           TEXT,
    card_data     JSONB,
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw           JSONB
);

CREATE INDEX IF NOT EXISTS hf_models_author_idx    ON hf_models (author);
CREATE INDEX IF NOT EXISTS hf_models_pipeline_idx  ON hf_models (pipeline_tag);
CREATE INDEX IF NOT EXISTS hf_models_downloads_idx ON hf_models (downloads_30d DESC);
CREATE INDEX IF NOT EXISTS hf_models_likes_idx     ON hf_models (likes DESC);
CREATE INDEX IF NOT EXISTS hf_models_modified_idx  ON hf_models (last_modified DESC);
CREATE INDEX IF NOT EXISTS hf_models_tags_gin      ON hf_models USING GIN (tags);

CREATE TABLE IF NOT EXISTS hf_datasets (
    id              TEXT PRIMARY KEY,
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

CREATE TABLE IF NOT EXISTS hf_checkpoints (
    username      TEXT PRIMARY KEY,
    status        TEXT NOT NULL DEFAULT 'pending',
    last_attempt  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_success  TIMESTAMPTZ,
    last_error    TEXT,
    attempt_count INT NOT NULL DEFAULT 0,
    last_job_id   TEXT
);

CREATE INDEX IF NOT EXISTS hf_checkpoints_status_idx ON hf_checkpoints (status);


-- ************************************************************
-- SECTION 3: LINKEDIN INGESTION (Layer 1 - Raw Data)
-- ************************************************************

CREATE TABLE IF NOT EXISTS ln_pending_urls (
    linkedin_url    TEXT PRIMARY KEY,
    source_platform VARCHAR(30) NOT NULL,
    source_username TEXT NOT NULL,
    priority        INT DEFAULT 1,
    status          VARCHAR(30) DEFAULT 'pending',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ln_pending_status_idx ON ln_pending_urls (status, priority);

CREATE TABLE IF NOT EXISTS ln_users (
    linkedin_url    TEXT PRIMARY KEY,
    full_name       TEXT,
    headline        TEXT,
    summary         TEXT,
    city            TEXT,
    country         TEXT,
    profile_pic_url TEXT,
    current_company TEXT,
    current_title   TEXT,
    industry        TEXT,
    num_connections INT,
    experiences     JSONB,
    education       JSONB,
    skills          TEXT[],
    certifications  JSONB,
    languages       TEXT[],
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw             JSONB
);

CREATE INDEX IF NOT EXISTS ln_users_ingested_idx ON ln_users (ingested_at DESC);

CREATE TABLE IF NOT EXISTS ln_checkpoints (
    linkedin_url  TEXT PRIMARY KEY,
    status        TEXT NOT NULL DEFAULT 'pending',
    last_attempt  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_success  TIMESTAMPTZ,
    last_error    TEXT,
    attempt_count INT NOT NULL DEFAULT 0,
    last_job_id   TEXT
);

CREATE INDEX IF NOT EXISTS ln_checkpoints_status_idx ON ln_checkpoints (status);


-- ************************************************************
-- SECTION 4: JOB TRACKING
-- ************************************************************

CREATE TABLE IF NOT EXISTS ingest_job (
    id                 TEXT PRIMARY KEY DEFAULT 'ij_' || gen_random_uuid(),
    job_type           VARCHAR(30) NOT NULL,
    platform           VARCHAR(30) NOT NULL,
    status             VARCHAR(30) NOT NULL DEFAULT 'pending',
    trigger            VARCHAR(30) NOT NULL DEFAULT 'api',
    triggered_by       TEXT,
    execution_phase_id TEXT,
    input_params       JSONB DEFAULT '{}'::jsonb,
    concurrency        INTEGER,
    started_at         TIMESTAMPTZ,
    completed_at       TIMESTAMPTZ,
    duration_ms        INTEGER,
    total_items        INTEGER DEFAULT 0,
    succeeded_count    INTEGER DEFAULT 0,
    failed_count       INTEGER DEFAULT 0,
    skipped_count      INTEGER DEFAULT 0,
    error_summary      TEXT,
    error_detail       JSONB,
    stats              JSONB DEFAULT '{}'::jsonb,
    is_deleted         BOOLEAN DEFAULT FALSE,
    created_at         TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at         TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ingest_job_status_idx   ON ingest_job (status);
CREATE INDEX IF NOT EXISTS ingest_job_type_idx     ON ingest_job (job_type);
CREATE INDEX IF NOT EXISTS ingest_job_platform_idx ON ingest_job (platform);
CREATE INDEX IF NOT EXISTS ingest_job_started_idx  ON ingest_job (started_at DESC);
CREATE INDEX IF NOT EXISTS ingest_job_phase_idx    ON ingest_job (execution_phase_id)
    WHERE execution_phase_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS ingest_job_item (
    id              TEXT PRIMARY KEY DEFAULT 'iji_' || gen_random_uuid(),
    job_id          TEXT NOT NULL REFERENCES ingest_job(id) ON DELETE CASCADE,
    login           TEXT NOT NULL,
    platform        VARCHAR(30) NOT NULL,
    status          VARCHAR(30) NOT NULL DEFAULT 'pending',
    attempt_number  INTEGER NOT NULL DEFAULT 1,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    duration_ms     INTEGER,
    records_written JSONB DEFAULT '{}'::jsonb,
    error_type      VARCHAR(30),
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at      TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ingest_job_item_job_idx    ON ingest_job_item (job_id);
CREATE INDEX IF NOT EXISTS ingest_job_item_login_idx  ON ingest_job_item (login);
CREATE INDEX IF NOT EXISTS ingest_job_item_status_idx ON ingest_job_item (status);
CREATE INDEX IF NOT EXISTS ingest_job_item_combo_idx  ON ingest_job_item (job_id, status);


-- ************************************************************
-- SECTION 5: PROFILE SYSTEM (Layers 2-4)
-- ************************************************************

-- Layer 2: Developer Profile (merged GH + HF)
CREATE TABLE IF NOT EXISTS developer_profile (
    id                    TEXT PRIMARY KEY DEFAULT 'dp_' || gen_random_uuid() NOT NULL,
    github_username       VARCHAR(255) UNIQUE,
    huggingface_username  VARCHAR(255) UNIQUE,
    email_hint            VARCHAR(320),
    ingestion_status      VARCHAR(30) NOT NULL DEFAULT 'pending',
    last_ingested_at      TIMESTAMPTZ,
    -- Merged GH+HF data
    display_name          VARCHAR(255),
    bio                   TEXT,
    avatar_url            VARCHAR(2048),
    company               VARCHAR(255),
    location              VARCHAR(500),
    website               VARCHAR(2048),
    total_repos           INTEGER DEFAULT 0,
    total_stars           INTEGER DEFAULT 0,
    total_contributions   INTEGER DEFAULT 0,
    total_followers       INTEGER DEFAULT 0,
    total_hf_models       INTEGER DEFAULT 0,
    total_hf_datasets     INTEGER DEFAULT 0,
    total_hf_spaces       INTEGER DEFAULT 0,
    total_hf_downloads    INTEGER DEFAULT 0,
    total_papers          INTEGER DEFAULT 0,
    languages             JSONB DEFAULT '[]'::jsonb,
    skills                JSONB DEFAULT '[]'::jsonb,
    topics                JSONB DEFAULT '[]'::jsonb,
    dev_source_priority   JSONB DEFAULT '{}'::jsonb,
    dev_merged_at         TIMESTAMPTZ,
    -- Audit
    is_deleted            BOOLEAN DEFAULT FALSE NOT NULL,
    created_by            TEXT,
    updated_by            TEXT,
    created_at            TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at            TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Layer 2: Social Profile (merged LN + X)
CREATE TABLE IF NOT EXISTS social_profile (
    id                     TEXT PRIMARY KEY DEFAULT 'sp_' || gen_random_uuid() NOT NULL,
    developer_profile_id   TEXT NOT NULL UNIQUE,
    linkedin_url           VARCHAR(2048) UNIQUE,
    x_handle               VARCHAR(255) UNIQUE,
    display_name           VARCHAR(255),
    headline               TEXT,
    bio                    TEXT,
    avatar_url             VARCHAR(2048),
    location               VARCHAR(500),
    current_title          VARCHAR(255),
    current_company        VARCHAR(255),
    industry               VARCHAR(255),
    years_of_experience    INTEGER,
    job_history            JSONB DEFAULT '[]'::jsonb,
    education              JSONB DEFAULT '[]'::jsonb,
    certifications         JSONB DEFAULT '[]'::jsonb,
    connections            INTEGER,
    skills                 JSONB DEFAULT '[]'::jsonb,
    social_source_priority JSONB DEFAULT '{}'::jsonb,
    social_merged_at       TIMESTAMPTZ,
    created_at             TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at             TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Layer 3: Aggregated Individual Profile (merged dev + social)
CREATE TABLE IF NOT EXISTS aggregated_individual_profile (
    id                    TEXT PRIMARY KEY DEFAULT 'aip_' || gen_random_uuid() NOT NULL,
    developer_profile_id  TEXT NOT NULL UNIQUE,
    -- From developer_profile (GH+HF)
    display_name          VARCHAR(255),
    bio                   TEXT,
    avatar_url            VARCHAR(2048),
    company               VARCHAR(255),
    location              VARCHAR(500),
    website               VARCHAR(2048),
    total_repos           INTEGER DEFAULT 0,
    total_stars           INTEGER DEFAULT 0,
    total_contributions   INTEGER DEFAULT 0,
    total_followers       INTEGER DEFAULT 0,
    total_hf_models       INTEGER DEFAULT 0,
    total_hf_datasets     INTEGER DEFAULT 0,
    total_hf_spaces       INTEGER DEFAULT 0,
    total_hf_downloads    INTEGER DEFAULT 0,
    total_papers          INTEGER DEFAULT 0,
    languages             JSONB DEFAULT '[]'::jsonb,
    skills                JSONB DEFAULT '[]'::jsonb,
    topics                JSONB DEFAULT '[]'::jsonb,
    -- From social_profile (LN+X)
    headline              TEXT,
    current_title         VARCHAR(255),
    current_company       VARCHAR(255),
    industry              VARCHAR(255),
    years_of_experience   INTEGER,
    job_history           JSONB DEFAULT '[]'::jsonb,
    education             JSONB DEFAULT '[]'::jsonb,
    certifications        JSONB DEFAULT '[]'::jsonb,
    connections           INTEGER,
    -- Merge metadata
    source_priority       JSONB DEFAULT '{}'::jsonb,
    aggregated_at         TIMESTAMPTZ,
    created_at            TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at            TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Layer 4: Cohesive Individual Profile (final enriched profile + embedding)
CREATE TABLE IF NOT EXISTS cohesive_individual_profile (
    id                           TEXT PRIMARY KEY DEFAULT 'cip_' || gen_random_uuid() NOT NULL,
    developer_profile_id         TEXT NOT NULL UNIQUE,
    display_name                 VARCHAR(255),
    bio                          TEXT,
    headline                     TEXT,
    location                     VARCHAR(500),
    avatar_url                   VARCHAR(2048),
    company                      VARCHAR(255),
    website                      VARCHAR(2048),
    total_repos                  INTEGER DEFAULT 0,
    total_stars                  INTEGER DEFAULT 0,
    total_contributions          INTEGER DEFAULT 0,
    total_followers              INTEGER DEFAULT 0,
    total_hf_models              INTEGER DEFAULT 0,
    total_hf_datasets            INTEGER DEFAULT 0,
    total_hf_spaces              INTEGER DEFAULT 0,
    total_hf_downloads           INTEGER DEFAULT 0,
    total_papers                 INTEGER DEFAULT 0,
    languages                    JSONB DEFAULT '[]'::jsonb,
    skills                       JSONB DEFAULT '[]'::jsonb,
    topics                       JSONB DEFAULT '[]'::jsonb,
    years_of_experience          INTEGER,
    current_title                VARCHAR(255),
    current_company              VARCHAR(255),
    job_history                  JSONB DEFAULT '[]'::jsonb,
    embedding_text               TEXT,
    search_tsv                   TSVECTOR,
    embedding_vector_id          VARCHAR(255),
    source_priority              JSONB DEFAULT '{}'::jsonb,
    merged_at                    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_cip_search_tsv
    ON cohesive_individual_profile USING GIN (search_tsv);

-- Profile Ranking (scores computed from cohesive profile)
CREATE TABLE IF NOT EXISTS profile_ranking (
    id                               TEXT PRIMARY KEY DEFAULT 'pr_' || gen_random_uuid() NOT NULL,
    cohesive_individual_profile_id   TEXT NOT NULL UNIQUE,
    github_activity_score            NUMERIC(5, 4) DEFAULT 0,
    technical_influence_score        NUMERIC(5, 4) DEFAULT 0,
    hiring_fit_score                 NUMERIC(5, 4) DEFAULT 0,
    experience_score                 NUMERIC(5, 4) DEFAULT 0,
    skills_breadth_score             NUMERIC(5, 4) DEFAULT 0,
    recency_score                    NUMERIC(5, 4) DEFAULT 0,
    oss_contribution_score           NUMERIC(5, 4) DEFAULT 0,
    hf_impact_score                  NUMERIC(5, 4) DEFAULT 0,
    composite_score                  NUMERIC(5, 4) DEFAULT 0,
    weight_config                    JSONB DEFAULT '{}'::jsonb,
    computed_at                      TIMESTAMPTZ DEFAULT NOW()
);

-- Merge Audit Log (field-level tracking at every merge level)
CREATE TABLE IF NOT EXISTS merge_audit_log (
    id                    TEXT PRIMARY KEY DEFAULT 'mal_' || gen_random_uuid() NOT NULL,
    developer_profile_id  TEXT NOT NULL,
    merge_level           VARCHAR(30) NOT NULL,
    target_table          VARCHAR(60) NOT NULL,
    merge_run_id          TEXT NOT NULL,
    field_name            VARCHAR(100) NOT NULL,
    winning_source        VARCHAR(30) NOT NULL,
    winning_value         TEXT,
    previous_value        TEXT,
    overridden_values     JSONB,
    action                VARCHAR(20) NOT NULL,
    merged_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS merge_audit_dp_idx    ON merge_audit_log (developer_profile_id, merged_at DESC);
CREATE INDEX IF NOT EXISTS merge_audit_run_idx   ON merge_audit_log (merge_run_id);
CREATE INDEX IF NOT EXISTS merge_audit_level_idx ON merge_audit_log (merge_level, action);

-- Profile system foreign keys
ALTER TABLE social_profile
    ADD CONSTRAINT sp_developer_profile_id_fk
    FOREIGN KEY (developer_profile_id) REFERENCES developer_profile(id);

ALTER TABLE aggregated_individual_profile
    ADD CONSTRAINT aip_developer_profile_id_fk
    FOREIGN KEY (developer_profile_id) REFERENCES developer_profile(id);

ALTER TABLE cohesive_individual_profile
    ADD CONSTRAINT cip_developer_profile_id_fk
    FOREIGN KEY (developer_profile_id) REFERENCES developer_profile(id);

ALTER TABLE profile_ranking
    ADD CONSTRAINT pr_cohesive_individual_profile_id_fk
    FOREIGN KEY (cohesive_individual_profile_id) REFERENCES cohesive_individual_profile(id);

-- Full-text search trigger (auto-populates search_tsv from embedding_text)
CREATE OR REPLACE FUNCTION cip_search_tsv_trigger()
RETURNS trigger AS $$
BEGIN
    NEW.search_tsv := to_tsvector('english', COALESCE(NEW.embedding_text, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_cip_search_tsv ON cohesive_individual_profile;
CREATE TRIGGER trg_cip_search_tsv
    BEFORE INSERT OR UPDATE OF embedding_text ON cohesive_individual_profile
    FOR EACH ROW
    EXECUTE FUNCTION cip_search_tsv_trigger();


-- ************************************************************
-- SECTION 6: EMAIL OUTREACH
-- ************************************************************

-- Enum types
DO $$ BEGIN CREATE TYPE mailbox_provider_enum AS ENUM ('gmail', 'outlook', 'smtp'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE mailbox_status_enum AS ENUM ('connected', 'disconnected', 'error', 'rate_limited'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE campaign_status_enum AS ENUM ('draft', 'active', 'paused', 'completed', 'cancelled'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE step_type_enum AS ENUM ('email', 'wait', 'condition'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE recipient_status_enum AS ENUM ('active', 'paused', 'completed', 'replied', 'bounced', 'unsubscribed', 'error'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE message_status_enum AS ENUM ('scheduled', 'queued', 'sending', 'sent', 'delivered', 'failed', 'cancelled', 'bounced'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE email_event_type_enum AS ENUM ('sent', 'delivered', 'opened', 'clicked', 'replied', 'bounced', 'unsubscribed', 'complained', 'failed'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE email_source_enum AS ENUM ('manual', 'github_public', 'github_commit', 'huggingface', 'hunter', 'apollo', 'other'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE send_provider_enum AS ENUM ('gmail_api', 'outlook_graph', 'smtp', 'sendgrid'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS mailbox (
    id                   TEXT PRIMARY KEY DEFAULT 'mbx_' || gen_random_uuid() NOT NULL,
    owner_id             TEXT NOT NULL,
    provider             VARCHAR(30) NOT NULL,
    email_address        VARCHAR(320) NOT NULL,
    display_name         VARCHAR(255),
    status               VARCHAR(30) NOT NULL DEFAULT 'connected',
    access_token         TEXT,
    refresh_token        TEXT,
    token_expires_at     TIMESTAMPTZ,
    smtp_host            VARCHAR(255),
    smtp_port            INTEGER,
    smtp_username        VARCHAR(255),
    smtp_password        TEXT,
    smtp_use_tls         BOOLEAN DEFAULT TRUE,
    daily_send_limit     INTEGER DEFAULT 35 NOT NULL,
    sends_today          INTEGER DEFAULT 0 NOT NULL,
    sends_today_reset_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    warmup_enabled       BOOLEAN DEFAULT FALSE,
    warmup_current_limit INTEGER DEFAULT 5,
    error_message        TEXT,
    last_error_at        TIMESTAMPTZ,
    metadata             JSONB DEFAULT '{}'::jsonb,
    is_deleted           BOOLEAN DEFAULT FALSE NOT NULL,
    created_by           TEXT,
    updated_by           TEXT,
    created_at           TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at           TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mailbox_owner  ON mailbox (owner_id);
CREATE INDEX IF NOT EXISTS idx_mailbox_email  ON mailbox (email_address);
CREATE INDEX IF NOT EXISTS idx_mailbox_status ON mailbox (status);

CREATE TABLE IF NOT EXISTS email_template (
    id         TEXT PRIMARY KEY DEFAULT 'etpl_' || gen_random_uuid() NOT NULL,
    owner_id   TEXT NOT NULL,
    name       VARCHAR(255) NOT NULL,
    category   VARCHAR(100),
    subject    TEXT NOT NULL,
    body_html  TEXT NOT NULL,
    body_text  TEXT,
    variables  JSONB DEFAULT '[]'::jsonb,
    metadata   JSONB DEFAULT '{}'::jsonb,
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
    created_by TEXT,
    updated_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_email_template_owner    ON email_template (owner_id);
CREATE INDEX IF NOT EXISTS idx_email_template_category ON email_template (category);

CREATE TABLE IF NOT EXISTS email_campaign (
    id                 TEXT PRIMARY KEY DEFAULT 'ec_' || gen_random_uuid() NOT NULL,
    owner_id           TEXT NOT NULL,
    mailbox_id         TEXT NOT NULL,
    name               VARCHAR(255) NOT NULL,
    description        TEXT,
    status             VARCHAR(30) NOT NULL DEFAULT 'draft',
    send_window_start  VARCHAR(5),
    send_window_end    VARCHAR(5),
    send_timezone      VARCHAR(50) DEFAULT 'UTC',
    send_days          JSONB DEFAULT '[1,2,3,4,5]'::jsonb,
    stop_on_reply      BOOLEAN DEFAULT TRUE,
    stop_on_bounce     BOOLEAN DEFAULT TRUE,
    track_opens        BOOLEAN DEFAULT TRUE,
    track_clicks       BOOLEAN DEFAULT TRUE,
    total_recipients   INTEGER DEFAULT 0 NOT NULL,
    total_sent         INTEGER DEFAULT 0 NOT NULL,
    total_delivered    INTEGER DEFAULT 0 NOT NULL,
    total_opened       INTEGER DEFAULT 0 NOT NULL,
    total_clicked      INTEGER DEFAULT 0 NOT NULL,
    total_replied      INTEGER DEFAULT 0 NOT NULL,
    total_bounced      INTEGER DEFAULT 0 NOT NULL,
    total_unsubscribed INTEGER DEFAULT 0 NOT NULL,
    started_at         TIMESTAMPTZ,
    completed_at       TIMESTAMPTZ,
    metadata           JSONB DEFAULT '{}'::jsonb,
    is_deleted         BOOLEAN DEFAULT FALSE NOT NULL,
    created_by         TEXT,
    updated_by         TEXT,
    created_at         TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at         TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_campaign_owner   ON email_campaign (owner_id);
CREATE INDEX IF NOT EXISTS idx_campaign_status  ON email_campaign (status);
CREATE INDEX IF NOT EXISTS idx_campaign_mailbox ON email_campaign (mailbox_id);

CREATE TABLE IF NOT EXISTS campaign_step (
    id               TEXT PRIMARY KEY DEFAULT 'cst_' || gen_random_uuid() NOT NULL,
    campaign_id      TEXT NOT NULL,
    template_id      TEXT,
    step_order       INTEGER NOT NULL,
    step_type        VARCHAR(30) NOT NULL DEFAULT 'email',
    delay_days       INTEGER DEFAULT 0 NOT NULL,
    delay_hours      INTEGER DEFAULT 0 NOT NULL,
    subject_override TEXT,
    body_override    TEXT,
    condition_field  VARCHAR(100),
    condition_op     VARCHAR(20),
    condition_value  VARCHAR(255),
    is_deleted       BOOLEAN DEFAULT FALSE NOT NULL,
    created_by       TEXT,
    updated_by       TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at       TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_step_campaign ON campaign_step (campaign_id);
CREATE INDEX IF NOT EXISTS idx_step_order    ON campaign_step (campaign_id, step_order);

CREATE TABLE IF NOT EXISTS campaign_recipient (
    id                   TEXT PRIMARY KEY DEFAULT 'cr_' || gen_random_uuid() NOT NULL,
    campaign_id          TEXT NOT NULL,
    developer_profile_id TEXT,
    email                VARCHAR(320) NOT NULL,
    first_name           VARCHAR(255),
    last_name            VARCHAR(255),
    company              VARCHAR(255),
    title                VARCHAR(255),
    status               VARCHAR(30) NOT NULL DEFAULT 'active',
    current_step_order   INTEGER DEFAULT 0 NOT NULL,
    next_send_at         TIMESTAMPTZ,
    email_source         VARCHAR(30),
    merge_variables      JSONB DEFAULT '{}'::jsonb,
    metadata             JSONB DEFAULT '{}'::jsonb,
    is_deleted           BOOLEAN DEFAULT FALSE NOT NULL,
    created_by           TEXT,
    updated_by           TEXT,
    created_at           TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at           TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_recipient_campaign  ON campaign_recipient (campaign_id);
CREATE INDEX IF NOT EXISTS idx_recipient_email     ON campaign_recipient (email);
CREATE INDEX IF NOT EXISTS idx_recipient_status    ON campaign_recipient (campaign_id, status);
CREATE INDEX IF NOT EXISTS idx_recipient_next_send ON campaign_recipient (next_send_at) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS email_message (
    id                  TEXT PRIMARY KEY DEFAULT 'em_' || gen_random_uuid() NOT NULL,
    campaign_id         TEXT NOT NULL,
    step_id             TEXT NOT NULL,
    recipient_id        TEXT NOT NULL,
    mailbox_id          TEXT NOT NULL,
    tracking_id         TEXT NOT NULL UNIQUE,
    from_email          VARCHAR(320) NOT NULL,
    from_name           VARCHAR(255),
    to_email            VARCHAR(320) NOT NULL,
    subject             TEXT NOT NULL,
    body_html           TEXT NOT NULL,
    body_text           TEXT,
    status              VARCHAR(30) NOT NULL DEFAULT 'scheduled',
    scheduled_at        TIMESTAMPTZ NOT NULL,
    sent_at             TIMESTAMPTZ,
    delivered_at        TIMESTAMPTZ,
    opened_at           TIMESTAMPTZ,
    clicked_at          TIMESTAMPTZ,
    replied_at          TIMESTAMPTZ,
    bounced_at          TIMESTAMPTZ,
    failed_at           TIMESTAMPTZ,
    provider            VARCHAR(30),
    provider_message_id TEXT,
    message_id_header   TEXT,
    thread_id           TEXT,
    in_reply_to         TEXT,
    link_map            JSONB DEFAULT '{}'::jsonb,
    open_count          INTEGER DEFAULT 0 NOT NULL,
    click_count         INTEGER DEFAULT 0 NOT NULL,
    retry_count         INTEGER DEFAULT 0 NOT NULL,
    max_retries         INTEGER DEFAULT 3 NOT NULL,
    next_retry_at       TIMESTAMPTZ,
    error_message       TEXT,
    metadata            JSONB DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at          TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_message_campaign   ON email_message (campaign_id);
CREATE INDEX IF NOT EXISTS idx_message_recipient  ON email_message (recipient_id);
CREATE INDEX IF NOT EXISTS idx_message_tracking   ON email_message (tracking_id);
CREATE INDEX IF NOT EXISTS idx_message_thread     ON email_message (thread_id);
CREATE INDEX IF NOT EXISTS idx_message_send_queue ON email_message (scheduled_at, status) WHERE status IN ('scheduled', 'queued');
CREATE INDEX IF NOT EXISTS idx_message_status     ON email_message (status);

CREATE TABLE IF NOT EXISTS email_event (
    id          TEXT PRIMARY KEY DEFAULT 'ee_' || gen_random_uuid() NOT NULL,
    message_id  TEXT NOT NULL,
    event_type  VARCHAR(30) NOT NULL,
    ip_address  VARCHAR(45),
    user_agent  TEXT,
    link_url    TEXT,
    raw_payload JSONB DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_event_message ON email_event (message_id);
CREATE INDEX IF NOT EXISTS idx_event_type    ON email_event (event_type);

CREATE TABLE IF NOT EXISTS email_unsubscribe (
    id         TEXT PRIMARY KEY DEFAULT 'unsub_' || gen_random_uuid() NOT NULL,
    email      VARCHAR(320) NOT NULL UNIQUE,
    reason     TEXT,
    source     VARCHAR(100),
    message_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_unsub_email ON email_unsubscribe (email);

-- Email outreach foreign keys
ALTER TABLE email_campaign
    ADD CONSTRAINT ec_mailbox_id_fk
    FOREIGN KEY (mailbox_id) REFERENCES mailbox(id);

ALTER TABLE campaign_step
    ADD CONSTRAINT cst_campaign_id_fk
    FOREIGN KEY (campaign_id) REFERENCES email_campaign(id);

ALTER TABLE campaign_step
    ADD CONSTRAINT cst_template_id_fk
    FOREIGN KEY (template_id) REFERENCES email_template(id);

ALTER TABLE campaign_recipient
    ADD CONSTRAINT cr_campaign_id_fk
    FOREIGN KEY (campaign_id) REFERENCES email_campaign(id);

ALTER TABLE campaign_recipient
    ADD CONSTRAINT cr_developer_profile_id_fk
    FOREIGN KEY (developer_profile_id) REFERENCES developer_profile(id);

ALTER TABLE email_message
    ADD CONSTRAINT em_campaign_id_fk
    FOREIGN KEY (campaign_id) REFERENCES email_campaign(id);

ALTER TABLE email_message
    ADD CONSTRAINT em_step_id_fk
    FOREIGN KEY (step_id) REFERENCES campaign_step(id);

ALTER TABLE email_message
    ADD CONSTRAINT em_recipient_id_fk
    FOREIGN KEY (recipient_id) REFERENCES campaign_recipient(id);

ALTER TABLE email_message
    ADD CONSTRAINT em_mailbox_id_fk
    FOREIGN KEY (mailbox_id) REFERENCES mailbox(id);

ALTER TABLE email_event
    ADD CONSTRAINT ee_message_id_fk
    FOREIGN KEY (message_id) REFERENCES email_message(id);


-- ************************************************************
-- SECTION 7: IDEMPOTENT MIGRATIONS (safe to re-run on existing DBs)
-- ************************************************************

-- Drop FK constraint on gh_commits.author_id (commit authors may not be ingested users)
ALTER TABLE gh_commits DROP CONSTRAINT IF EXISTS gh_commits_author_id_fkey;

-- Backfill search_tsv for existing cohesive profiles
UPDATE cohesive_individual_profile
SET search_tsv = to_tsvector('english', COALESCE(embedding_text, ''))
WHERE search_tsv IS NULL AND embedding_text IS NOT NULL;
