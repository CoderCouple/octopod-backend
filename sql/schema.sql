-- ============================================================
-- Octopod Backend - Database Schema
-- Crowdsourced Org Graph System
-- ============================================================

-- =========================
-- ENUM TYPES
-- =========================

CREATE TYPE relationship_type_enum AS ENUM (
  'solid_line',
  'dotted_line',
  'matrix'
);

CREATE TYPE relationship_status_enum AS ENUM (
  'confirmed',
  'probable',
  'weak'
);

CREATE TYPE career_event_type_enum AS ENUM (
  'join',
  'leave',
  'promotion',
  'transfer',
  'title_change',
  'manager_change',
  'role_change'
);

CREATE TYPE claim_state_enum AS ENUM (
  'draft',
  'submitted',
  'validation',
  'pending_counterparty',
  'pending_moderation',
  'verified',
  'rejected',
  'expired',
  'disputed',
  'superseded'
);

CREATE TYPE evidence_type_enum AS ENUM (
  'self_claim',
  'manager_confirmation',
  'peer_confirmation',
  'system',
  'rejection'
);

CREATE TYPE evidence_response_enum AS ENUM (
  'confirm',
  'reject',
  'abstain'
);

CREATE TYPE entity_type_enum AS ENUM (
  'org',
  'employee',
  'employment',
  'reporting_relationship',
  'career_event',
  'reporting_claim'
);

CREATE TYPE visibility_level_enum AS ENUM ('0', '1', '2', '3');

-- =========================
-- TABLES
-- =========================

--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "organization" (
    "id"            TEXT PRIMARY KEY DEFAULT 'org_' || gen_random_uuid() NOT NULL,
    "name"          VARCHAR(255) NOT NULL,
    "domain"        VARCHAR(255) UNIQUE,
    "industry"      VARCHAR(255),
    "logo_url"      VARCHAR(2048),
    "metadata"      JSONB DEFAULT '{}'::jsonb,
    "is_deleted"    BOOLEAN DEFAULT FALSE NOT NULL,
    "created_by"    TEXT,
    "updated_by"    TEXT,
    "created_at"    TIMESTAMPTZ DEFAULT now() NOT NULL,
    "updated_at"    TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_organization_name" ON "organization" ("name");

--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "employee" (
    "id"              TEXT PRIMARY KEY DEFAULT 'emp_' || gen_random_uuid() NOT NULL,
    "canonical_name"  VARCHAR(255) NOT NULL,
    "primary_email"   VARCHAR(320) UNIQUE,
    "profile_data"    JSONB DEFAULT '{}'::jsonb,
    "is_deleted"      BOOLEAN DEFAULT FALSE NOT NULL,
    "created_by"      TEXT,
    "updated_by"      TEXT,
    "created_at"      TIMESTAMPTZ DEFAULT now() NOT NULL,
    "updated_at"      TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_employee_canonical_name" ON "employee" ("canonical_name");

--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "employment" (
    "id"            TEXT PRIMARY KEY DEFAULT 'empl_' || gen_random_uuid() NOT NULL,
    "employee_id"   TEXT NOT NULL,
    "org_id"        TEXT NOT NULL,
    "title"         VARCHAR(255),
    "department"    VARCHAR(255),
    "level"         VARCHAR(100),
    "location"      VARCHAR(255),
    "valid_from"    TIMESTAMPTZ,
    "valid_to"      TIMESTAMPTZ,
    "is_current"    BOOLEAN DEFAULT TRUE NOT NULL,
    "is_deleted"    BOOLEAN DEFAULT FALSE NOT NULL,
    "created_by"    TEXT,
    "updated_by"    TEXT,
    "created_at"    TIMESTAMPTZ DEFAULT now() NOT NULL,
    "updated_at"    TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_employment_employee_org" ON "employment" ("employee_id", "org_id");

--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "reporting_relationship" (
    "id"                    TEXT PRIMARY KEY DEFAULT 'rr_' || gen_random_uuid() NOT NULL,
    "org_id"                TEXT NOT NULL,
    "employee_id"           TEXT NOT NULL,
    "manager_employee_id"   TEXT NOT NULL,
    "relationship_type"     VARCHAR(20) NOT NULL DEFAULT 'solid_line',
    "status"                VARCHAR(20) NOT NULL DEFAULT 'weak',
    "confidence_score"      NUMERIC(5, 4) NOT NULL DEFAULT 0.0,
    "valid_from"            TIMESTAMPTZ,
    "valid_to"              TIMESTAMPTZ,
    "is_current"            BOOLEAN DEFAULT TRUE NOT NULL,
    "is_deleted"            BOOLEAN DEFAULT FALSE NOT NULL,
    "created_by"            TEXT,
    "updated_by"            TEXT,
    "created_at"            TIMESTAMPTZ DEFAULT now() NOT NULL,
    "updated_at"            TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_rr_org_employee" ON "reporting_relationship" ("org_id", "employee_id");
CREATE INDEX IF NOT EXISTS "idx_rr_manager" ON "reporting_relationship" ("manager_employee_id");

--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "career_event" (
    "id"              TEXT PRIMARY KEY DEFAULT 'ce_' || gen_random_uuid() NOT NULL,
    "employee_id"     TEXT NOT NULL,
    "org_id"          TEXT,
    "employment_id"   TEXT,
    "event_type"      VARCHAR(30) NOT NULL,
    "effective_at"    TIMESTAMPTZ NOT NULL,
    "recorded_at"     TIMESTAMPTZ DEFAULT now() NOT NULL,
    "payload"         JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS "idx_career_event_employee_id" ON "career_event" ("employee_id");

--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "event_log" (
    "id"            TEXT PRIMARY KEY DEFAULT 'evt_' || gen_random_uuid() NOT NULL,
    "sequence_no"   INTEGER NOT NULL,
    "entity_type"   VARCHAR(50) NOT NULL,
    "entity_id"     TEXT NOT NULL,
    "action"        VARCHAR(50) NOT NULL,
    "before_state"  JSONB,
    "after_state"   JSONB,
    "actor_id"      TEXT,
    "timestamp"     TIMESTAMPTZ DEFAULT now() NOT NULL,
    "prev_hash"     TEXT,
    "event_hash"    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_event_log_sequence_no" ON "event_log" ("sequence_no");
CREATE INDEX IF NOT EXISTS "idx_event_log_entity" ON "event_log" ("entity_type", "entity_id");
CREATE INDEX IF NOT EXISTS "idx_event_log_actor_id" ON "event_log" ("actor_id");

--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "reporting_claim" (
    "id"                TEXT PRIMARY KEY DEFAULT 'claim_' || gen_random_uuid() NOT NULL,
    "org_id"            TEXT NOT NULL,
    "employee_id"       TEXT NOT NULL,
    "manager_id"        TEXT NOT NULL,
    "claimant_id"       TEXT NOT NULL,
    "state"             VARCHAR(30) NOT NULL DEFAULT 'draft',
    "confidence_score"  NUMERIC(5, 4) DEFAULT 0.0,
    "submitted_at"      TIMESTAMPTZ,
    "resolved_at"       TIMESTAMPTZ,
    "expires_at"        TIMESTAMPTZ,
    "superseded_by"     TEXT,
    "is_deleted"        BOOLEAN DEFAULT FALSE NOT NULL,
    "created_by"        TEXT,
    "updated_by"        TEXT,
    "created_at"        TIMESTAMPTZ DEFAULT now() NOT NULL,
    "updated_at"        TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_claim_employee_manager" ON "reporting_claim" ("employee_id", "manager_id");
CREATE INDEX IF NOT EXISTS "idx_claim_state" ON "reporting_claim" ("state");
CREATE INDEX IF NOT EXISTS "idx_claim_claimant" ON "reporting_claim" ("claimant_id");

--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "claim_evidence" (
    "id"              TEXT PRIMARY KEY DEFAULT 'evi_' || gen_random_uuid() NOT NULL,
    "claim_id"        TEXT NOT NULL,
    "actor_id"        TEXT NOT NULL,
    "evidence_type"   VARCHAR(30) NOT NULL,
    "response"        VARCHAR(20),
    "weight"          NUMERIC(5, 4),
    "comment"         VARCHAR(1000),
    "created_at"      TIMESTAMPTZ DEFAULT now() NOT NULL
);

--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "contributor_score" (
    "id"                        TEXT PRIMARY KEY DEFAULT 'cs_' || gen_random_uuid() NOT NULL,
    "actor_id"                  TEXT UNIQUE NOT NULL,
    "total_claims_submitted"    INTEGER DEFAULT 0 NOT NULL,
    "total_claims_verified"     INTEGER DEFAULT 0 NOT NULL,
    "total_confirmations_given" INTEGER DEFAULT 0 NOT NULL,
    "total_rejections_given"    INTEGER DEFAULT 0 NOT NULL,
    "visibility_level"          INTEGER DEFAULT 0 NOT NULL,
    "raw_score"                 NUMERIC(10, 2) DEFAULT 0 NOT NULL,
    "created_at"                TIMESTAMPTZ DEFAULT now() NOT NULL,
    "updated_at"                TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- =========================
-- FOREIGN KEYS
-- =========================

--> statement-breakpoint
ALTER TABLE "employment"
  ADD CONSTRAINT "employment_employee_id_fk"
    FOREIGN KEY ("employee_id") REFERENCES "employee" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE "employment"
  ADD CONSTRAINT "employment_org_id_fk"
    FOREIGN KEY ("org_id") REFERENCES "organization" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

--> statement-breakpoint
ALTER TABLE "reporting_relationship"
  ADD CONSTRAINT "rr_org_id_fk"
    FOREIGN KEY ("org_id") REFERENCES "organization" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE "reporting_relationship"
  ADD CONSTRAINT "rr_employee_id_fk"
    FOREIGN KEY ("employee_id") REFERENCES "employee" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE "reporting_relationship"
  ADD CONSTRAINT "rr_manager_employee_id_fk"
    FOREIGN KEY ("manager_employee_id") REFERENCES "employee" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

--> statement-breakpoint
ALTER TABLE "career_event"
  ADD CONSTRAINT "career_event_employee_id_fk"
    FOREIGN KEY ("employee_id") REFERENCES "employee" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE "career_event"
  ADD CONSTRAINT "career_event_org_id_fk"
    FOREIGN KEY ("org_id") REFERENCES "organization" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE "career_event"
  ADD CONSTRAINT "career_event_employment_id_fk"
    FOREIGN KEY ("employment_id") REFERENCES "employment" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

--> statement-breakpoint
ALTER TABLE "reporting_claim"
  ADD CONSTRAINT "reporting_claim_org_id_fk"
    FOREIGN KEY ("org_id") REFERENCES "organization" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE "reporting_claim"
  ADD CONSTRAINT "reporting_claim_employee_id_fk"
    FOREIGN KEY ("employee_id") REFERENCES "employee" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE "reporting_claim"
  ADD CONSTRAINT "reporting_claim_manager_id_fk"
    FOREIGN KEY ("manager_id") REFERENCES "employee" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE "reporting_claim"
  ADD CONSTRAINT "reporting_claim_superseded_by_fk"
    FOREIGN KEY ("superseded_by") REFERENCES "reporting_claim" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

--> statement-breakpoint
ALTER TABLE "claim_evidence"
  ADD CONSTRAINT "claim_evidence_claim_id_fk"
    FOREIGN KEY ("claim_id") REFERENCES "reporting_claim" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- =========================
-- SEED DATA
-- =========================

-- Sample organization
INSERT INTO "organization" (id, name, domain, industry, created_by, updated_by)
VALUES (
  'org_00000000-0000-0000-0000-000000000001',
  'Acme Corp',
  'acme.com',
  'Technology',
  'system',
  'system'
);

-- Sample employees
INSERT INTO "employee" (id, canonical_name, primary_email, created_by, updated_by)
VALUES
  ('emp_00000000-0000-0000-0000-000000000001', 'Alice Johnson', 'alice@acme.com', 'system', 'system'),
  ('emp_00000000-0000-0000-0000-000000000002', 'Bob Smith', 'bob@acme.com', 'system', 'system'),
  ('emp_00000000-0000-0000-0000-000000000003', 'Carol Davis', 'carol@acme.com', 'system', 'system');

-- Sample employments
INSERT INTO "employment" (id, employee_id, org_id, title, department, is_current, created_by, updated_by)
VALUES
  ('empl_00000000-0000-0000-0000-000000000001', 'emp_00000000-0000-0000-0000-000000000001', 'org_00000000-0000-0000-0000-000000000001', 'VP Engineering', 'Engineering', TRUE, 'system', 'system'),
  ('empl_00000000-0000-0000-0000-000000000002', 'emp_00000000-0000-0000-0000-000000000002', 'org_00000000-0000-0000-0000-000000000001', 'Senior Engineer', 'Engineering', TRUE, 'system', 'system'),
  ('empl_00000000-0000-0000-0000-000000000003', 'emp_00000000-0000-0000-0000-000000000003', 'org_00000000-0000-0000-0000-000000000001', 'Product Manager', 'Product', TRUE, 'system', 'system');

-- Sample reporting relationship (Bob reports to Alice)
INSERT INTO "reporting_relationship" (id, org_id, employee_id, manager_employee_id, relationship_type, status, confidence_score, is_current, created_by, updated_by)
VALUES (
  'rr_00000000-0000-0000-0000-000000000001',
  'org_00000000-0000-0000-0000-000000000001',
  'emp_00000000-0000-0000-0000-000000000002',
  'emp_00000000-0000-0000-0000-000000000001',
  'solid_line',
  'confirmed',
  0.9500,
  TRUE,
  'system',
  'system'
);
