-- ============================================================
-- Octopod Backend - Email Outreach Schema
-- Multi-step email sequences with tracking
-- ============================================================

-- =========================
-- ENUM TYPES
-- =========================

CREATE TYPE mailbox_provider_enum AS ENUM (
  'gmail',
  'outlook',
  'smtp'
);

CREATE TYPE mailbox_status_enum AS ENUM (
  'connected',
  'disconnected',
  'error',
  'rate_limited'
);

CREATE TYPE campaign_status_enum AS ENUM (
  'draft',
  'active',
  'paused',
  'completed',
  'cancelled'
);

CREATE TYPE step_type_enum AS ENUM (
  'email',
  'wait',
  'condition'
);

CREATE TYPE recipient_status_enum AS ENUM (
  'active',
  'paused',
  'completed',
  'replied',
  'bounced',
  'unsubscribed',
  'error'
);

CREATE TYPE message_status_enum AS ENUM (
  'scheduled',
  'queued',
  'sending',
  'sent',
  'delivered',
  'failed',
  'cancelled',
  'bounced'
);

CREATE TYPE email_event_type_enum AS ENUM (
  'sent',
  'delivered',
  'opened',
  'clicked',
  'replied',
  'bounced',
  'unsubscribed',
  'complained',
  'failed'
);

CREATE TYPE email_source_enum AS ENUM (
  'manual',
  'github_public',
  'github_commit',
  'huggingface',
  'hunter',
  'apollo',
  'other'
);

CREATE TYPE send_provider_enum AS ENUM (
  'gmail_api',
  'outlook_graph',
  'smtp',
  'sendgrid'
);

-- =========================
-- TABLES
-- =========================

--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "mailbox" (
    "id"                    TEXT PRIMARY KEY DEFAULT 'mbx_' || gen_random_uuid() NOT NULL,
    "owner_id"              TEXT NOT NULL,
    "provider"              VARCHAR(30) NOT NULL,
    "email_address"         VARCHAR(320) NOT NULL,
    "display_name"          VARCHAR(255),
    "status"                VARCHAR(30) NOT NULL DEFAULT 'connected',
    "access_token"          TEXT,
    "refresh_token"         TEXT,
    "token_expires_at"      TIMESTAMPTZ,
    "smtp_host"             VARCHAR(255),
    "smtp_port"             INTEGER,
    "smtp_username"         VARCHAR(255),
    "smtp_password"         TEXT,
    "smtp_use_tls"          BOOLEAN DEFAULT TRUE,
    "daily_send_limit"      INTEGER DEFAULT 35 NOT NULL,
    "sends_today"           INTEGER DEFAULT 0 NOT NULL,
    "sends_today_reset_at"  TIMESTAMPTZ DEFAULT now() NOT NULL,
    "warmup_enabled"        BOOLEAN DEFAULT FALSE,
    "warmup_current_limit"  INTEGER DEFAULT 5,
    "error_message"         TEXT,
    "last_error_at"         TIMESTAMPTZ,
    "metadata"              JSONB DEFAULT '{}'::jsonb,
    "is_deleted"            BOOLEAN DEFAULT FALSE NOT NULL,
    "created_by"            TEXT,
    "updated_by"            TEXT,
    "created_at"            TIMESTAMPTZ DEFAULT now() NOT NULL,
    "updated_at"            TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_mailbox_owner" ON "mailbox" ("owner_id");
CREATE INDEX IF NOT EXISTS "idx_mailbox_email" ON "mailbox" ("email_address");
CREATE INDEX IF NOT EXISTS "idx_mailbox_status" ON "mailbox" ("status");

--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "email_template" (
    "id"            TEXT PRIMARY KEY DEFAULT 'etpl_' || gen_random_uuid() NOT NULL,
    "owner_id"      TEXT NOT NULL,
    "name"          VARCHAR(255) NOT NULL,
    "category"      VARCHAR(100),
    "subject"       TEXT NOT NULL,
    "body_html"     TEXT NOT NULL,
    "body_text"     TEXT,
    "variables"     JSONB DEFAULT '[]'::jsonb,
    "metadata"      JSONB DEFAULT '{}'::jsonb,
    "is_deleted"    BOOLEAN DEFAULT FALSE NOT NULL,
    "created_by"    TEXT,
    "updated_by"    TEXT,
    "created_at"    TIMESTAMPTZ DEFAULT now() NOT NULL,
    "updated_at"    TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_email_template_owner" ON "email_template" ("owner_id");
CREATE INDEX IF NOT EXISTS "idx_email_template_category" ON "email_template" ("category");

--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "email_campaign" (
    "id"                    TEXT PRIMARY KEY DEFAULT 'ec_' || gen_random_uuid() NOT NULL,
    "owner_id"              TEXT NOT NULL,
    "mailbox_id"            TEXT NOT NULL,
    "name"                  VARCHAR(255) NOT NULL,
    "description"           TEXT,
    "status"                VARCHAR(30) NOT NULL DEFAULT 'draft',
    "send_window_start"     VARCHAR(5),
    "send_window_end"       VARCHAR(5),
    "send_timezone"         VARCHAR(50) DEFAULT 'UTC',
    "send_days"             JSONB DEFAULT '[1,2,3,4,5]'::jsonb,
    "stop_on_reply"         BOOLEAN DEFAULT TRUE,
    "stop_on_bounce"        BOOLEAN DEFAULT TRUE,
    "track_opens"           BOOLEAN DEFAULT TRUE,
    "track_clicks"          BOOLEAN DEFAULT TRUE,
    "total_recipients"      INTEGER DEFAULT 0 NOT NULL,
    "total_sent"            INTEGER DEFAULT 0 NOT NULL,
    "total_delivered"       INTEGER DEFAULT 0 NOT NULL,
    "total_opened"          INTEGER DEFAULT 0 NOT NULL,
    "total_clicked"         INTEGER DEFAULT 0 NOT NULL,
    "total_replied"         INTEGER DEFAULT 0 NOT NULL,
    "total_bounced"         INTEGER DEFAULT 0 NOT NULL,
    "total_unsubscribed"    INTEGER DEFAULT 0 NOT NULL,
    "started_at"            TIMESTAMPTZ,
    "completed_at"          TIMESTAMPTZ,
    "metadata"              JSONB DEFAULT '{}'::jsonb,
    "is_deleted"            BOOLEAN DEFAULT FALSE NOT NULL,
    "created_by"            TEXT,
    "updated_by"            TEXT,
    "created_at"            TIMESTAMPTZ DEFAULT now() NOT NULL,
    "updated_at"            TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_campaign_owner" ON "email_campaign" ("owner_id");
CREATE INDEX IF NOT EXISTS "idx_campaign_status" ON "email_campaign" ("status");
CREATE INDEX IF NOT EXISTS "idx_campaign_mailbox" ON "email_campaign" ("mailbox_id");

--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "campaign_step" (
    "id"                TEXT PRIMARY KEY DEFAULT 'cst_' || gen_random_uuid() NOT NULL,
    "campaign_id"       TEXT NOT NULL,
    "template_id"       TEXT,
    "step_order"        INTEGER NOT NULL,
    "step_type"         VARCHAR(30) NOT NULL DEFAULT 'email',
    "delay_days"        INTEGER DEFAULT 0 NOT NULL,
    "delay_hours"       INTEGER DEFAULT 0 NOT NULL,
    "subject_override"  TEXT,
    "body_override"     TEXT,
    "condition_field"   VARCHAR(100),
    "condition_op"      VARCHAR(20),
    "condition_value"   VARCHAR(255),
    "is_deleted"        BOOLEAN DEFAULT FALSE NOT NULL,
    "created_by"        TEXT,
    "updated_by"        TEXT,
    "created_at"        TIMESTAMPTZ DEFAULT now() NOT NULL,
    "updated_at"        TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_step_campaign" ON "campaign_step" ("campaign_id");
CREATE INDEX IF NOT EXISTS "idx_step_order" ON "campaign_step" ("campaign_id", "step_order");

--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "campaign_recipient" (
    "id"                    TEXT PRIMARY KEY DEFAULT 'cr_' || gen_random_uuid() NOT NULL,
    "campaign_id"           TEXT NOT NULL,
    "developer_profile_id"  TEXT,
    "email"                 VARCHAR(320) NOT NULL,
    "first_name"            VARCHAR(255),
    "last_name"             VARCHAR(255),
    "company"               VARCHAR(255),
    "title"                 VARCHAR(255),
    "status"                VARCHAR(30) NOT NULL DEFAULT 'active',
    "current_step_order"    INTEGER DEFAULT 0 NOT NULL,
    "next_send_at"          TIMESTAMPTZ,
    "email_source"          VARCHAR(30),
    "merge_variables"       JSONB DEFAULT '{}'::jsonb,
    "metadata"              JSONB DEFAULT '{}'::jsonb,
    "is_deleted"            BOOLEAN DEFAULT FALSE NOT NULL,
    "created_by"            TEXT,
    "updated_by"            TEXT,
    "created_at"            TIMESTAMPTZ DEFAULT now() NOT NULL,
    "updated_at"            TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_recipient_campaign" ON "campaign_recipient" ("campaign_id");
CREATE INDEX IF NOT EXISTS "idx_recipient_email" ON "campaign_recipient" ("email");
CREATE INDEX IF NOT EXISTS "idx_recipient_status" ON "campaign_recipient" ("campaign_id", "status");
CREATE INDEX IF NOT EXISTS "idx_recipient_next_send" ON "campaign_recipient" ("next_send_at") WHERE "status" = 'active';

--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "email_message" (
    "id"                    TEXT PRIMARY KEY DEFAULT 'em_' || gen_random_uuid() NOT NULL,
    "campaign_id"           TEXT NOT NULL,
    "step_id"               TEXT NOT NULL,
    "recipient_id"          TEXT NOT NULL,
    "mailbox_id"            TEXT NOT NULL,
    "tracking_id"           TEXT NOT NULL UNIQUE,
    "from_email"            VARCHAR(320) NOT NULL,
    "from_name"             VARCHAR(255),
    "to_email"              VARCHAR(320) NOT NULL,
    "subject"               TEXT NOT NULL,
    "body_html"             TEXT NOT NULL,
    "body_text"             TEXT,
    "status"                VARCHAR(30) NOT NULL DEFAULT 'scheduled',
    "scheduled_at"          TIMESTAMPTZ NOT NULL,
    "sent_at"               TIMESTAMPTZ,
    "delivered_at"          TIMESTAMPTZ,
    "opened_at"             TIMESTAMPTZ,
    "clicked_at"            TIMESTAMPTZ,
    "replied_at"            TIMESTAMPTZ,
    "bounced_at"            TIMESTAMPTZ,
    "failed_at"             TIMESTAMPTZ,
    "provider"              VARCHAR(30),
    "provider_message_id"   TEXT,
    "message_id_header"     TEXT,
    "thread_id"             TEXT,
    "in_reply_to"           TEXT,
    "link_map"              JSONB DEFAULT '{}'::jsonb,
    "open_count"            INTEGER DEFAULT 0 NOT NULL,
    "click_count"           INTEGER DEFAULT 0 NOT NULL,
    "retry_count"           INTEGER DEFAULT 0 NOT NULL,
    "max_retries"           INTEGER DEFAULT 3 NOT NULL,
    "next_retry_at"         TIMESTAMPTZ,
    "error_message"         TEXT,
    "metadata"              JSONB DEFAULT '{}'::jsonb,
    "created_at"            TIMESTAMPTZ DEFAULT now() NOT NULL,
    "updated_at"            TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_message_campaign" ON "email_message" ("campaign_id");
CREATE INDEX IF NOT EXISTS "idx_message_recipient" ON "email_message" ("recipient_id");
CREATE INDEX IF NOT EXISTS "idx_message_tracking" ON "email_message" ("tracking_id");
CREATE INDEX IF NOT EXISTS "idx_message_thread" ON "email_message" ("thread_id");
CREATE INDEX IF NOT EXISTS "idx_message_send_queue" ON "email_message" ("scheduled_at", "status") WHERE "status" IN ('scheduled', 'queued');
CREATE INDEX IF NOT EXISTS "idx_message_status" ON "email_message" ("status");

--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "email_event" (
    "id"            TEXT PRIMARY KEY DEFAULT 'ee_' || gen_random_uuid() NOT NULL,
    "message_id"    TEXT NOT NULL,
    "event_type"    VARCHAR(30) NOT NULL,
    "ip_address"    VARCHAR(45),
    "user_agent"    TEXT,
    "link_url"      TEXT,
    "raw_payload"   JSONB DEFAULT '{}'::jsonb,
    "created_at"    TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_event_message" ON "email_event" ("message_id");
CREATE INDEX IF NOT EXISTS "idx_event_type" ON "email_event" ("event_type");

--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "email_unsubscribe" (
    "id"            TEXT PRIMARY KEY DEFAULT 'unsub_' || gen_random_uuid() NOT NULL,
    "email"         VARCHAR(320) NOT NULL UNIQUE,
    "reason"        TEXT,
    "source"        VARCHAR(100),
    "message_id"    TEXT,
    "created_at"    TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_unsub_email" ON "email_unsubscribe" ("email");

-- =========================
-- FOREIGN KEYS
-- =========================

--> statement-breakpoint
ALTER TABLE "email_campaign"
  ADD CONSTRAINT "ec_mailbox_id_fk"
    FOREIGN KEY ("mailbox_id") REFERENCES "mailbox" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

--> statement-breakpoint
ALTER TABLE "campaign_step"
  ADD CONSTRAINT "cst_campaign_id_fk"
    FOREIGN KEY ("campaign_id") REFERENCES "email_campaign" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE "campaign_step"
  ADD CONSTRAINT "cst_template_id_fk"
    FOREIGN KEY ("template_id") REFERENCES "email_template" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

--> statement-breakpoint
ALTER TABLE "campaign_recipient"
  ADD CONSTRAINT "cr_campaign_id_fk"
    FOREIGN KEY ("campaign_id") REFERENCES "email_campaign" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE "campaign_recipient"
  ADD CONSTRAINT "cr_developer_profile_id_fk"
    FOREIGN KEY ("developer_profile_id") REFERENCES "developer_profile" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

--> statement-breakpoint
ALTER TABLE "email_message"
  ADD CONSTRAINT "em_campaign_id_fk"
    FOREIGN KEY ("campaign_id") REFERENCES "email_campaign" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE "email_message"
  ADD CONSTRAINT "em_step_id_fk"
    FOREIGN KEY ("step_id") REFERENCES "campaign_step" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE "email_message"
  ADD CONSTRAINT "em_recipient_id_fk"
    FOREIGN KEY ("recipient_id") REFERENCES "campaign_recipient" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE "email_message"
  ADD CONSTRAINT "em_mailbox_id_fk"
    FOREIGN KEY ("mailbox_id") REFERENCES "mailbox" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

--> statement-breakpoint
ALTER TABLE "email_event"
  ADD CONSTRAINT "ee_message_id_fk"
    FOREIGN KEY ("message_id") REFERENCES "email_message" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
