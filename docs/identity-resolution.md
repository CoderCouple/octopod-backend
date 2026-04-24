╭─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Plan to implement                                                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ Plan: Tiered Identity Resolution System                                                                                                                                                             │
│                                                                                                                                                                                                     │
│ Context                                                                                                                                                                                             │
│                                                                                                                                                                                                     │
│ The bridge sync system merges GH + HF + LN profiles through a 4-layer pipeline (raw → domain → aggregated → cohesive). Currently, identity resolution is exact-match only on                        │
│ hf_users.github_username → gh_users.login in BridgeStorage.upsert_developer_profile(). This misses matches via email, social handles, website cross-references, and name similarity — leading to    │
│ duplicate developer_profile rows for the same person.                                                                                                                                               │
│                                                                                                                                                                                                     │
│ This adds a multi-signal scoring system: auto-merge high-confidence matches (≥0.7), queue borderline matches (0.4–0.7) for manual review via a DB-backed merge_candidate table, and integrate as a  │
│ pipeline step.                                                                                                                                                                                      │
│                                                                                                                                                                                                     │
│ AWS note: The review queue uses a DB table (not SQS) because it requires queryable state — filtering by score, listing pending items, approve/reject workflows. SQS is fire-and-forget. AWS         │
│ services (SQS, EventBridge) are better suited for the pipeline scheduler refactor (future work).                                                                                                    │
│                                                                                                                                                                                                     │
│ Signal Weights & Thresholds                                                                                                                                                                         │
│                                                                                                                                                                                                     │
│ ┌───────────────────────────────────────────────────────────────────────┬────────┬───────────────┐                                                                                                  │
│ │                                Signal                                 │ Weight │     Type      │                                                                                                  │
│ ├───────────────────────────────────────────────────────────────────────┼────────┼───────────────┤                                                                                                  │
│ │ hf_github_exact — HF reports matching GH login                        │ 1.0    │ Deterministic │                                                                                                  │
│ ├───────────────────────────────────────────────────────────────────────┼────────┼───────────────┤                                                                                                  │
│ │ email_exact — gh_users.email matches cross-platform                   │ 0.9    │ Deterministic │                                                                                                  │
│ ├───────────────────────────────────────────────────────────────────────┼────────┼───────────────┤                                                                                                  │
│ │ twitter_exact — same handle (case-insensitive, strip @)               │ 0.85   │ Deterministic │                                                                                                  │
│ ├───────────────────────────────────────────────────────────────────────┼────────┼───────────────┤                                                                                                  │
│ │ website_crossref — GH website has huggingface.co/{user} or vice versa │ 0.8    │ Deterministic │                                                                                                  │
│ ├───────────────────────────────────────────────────────────────────────┼────────┼───────────────┤                                                                                                  │
│ │ linkedin_url_match — both link to same LN URL                         │ 0.75   │ Deterministic │                                                                                                  │
│ ├───────────────────────────────────────────────────────────────────────┼────────┼───────────────┤                                                                                                  │
│ │ avatar_gravatar_match — same Gravatar hash (non-default only)         │ 0.7    │ Heuristic     │                                                                                                  │
│ ├───────────────────────────────────────────────────────────────────────┼────────┼───────────────┤                                                                                                  │
│ │ name_location_exact — normalized names + locations match              │ 0.6    │ Heuristic     │                                                                                                  │
│ ├───────────────────────────────────────────────────────────────────────┼────────┼───────────────┤                                                                                                  │
│ │ name_company_fuzzy — Jaro-Winkler ≥0.9 + company match                │ 0.55   │ Fuzzy         │                                                                                                  │
│ ├───────────────────────────────────────────────────────────────────────┼────────┼───────────────┤                                                                                                  │
│ │ name_fuzzy_alone — Jaro-Winkler ≥0.9, no corroboration                │ 0.3    │ Fuzzy         │                                                                                                  │
│ └───────────────────────────────────────────────────────────────────────┴────────┴───────────────┘                                                                                                  │
│                                                                                                                                                                                                     │
│ Score = max(signal_weights) — a single deterministic match suffices.                                                                                                                                │
│                                                                                                                                                                                                     │
│ - ≥ 0.7 → Auto-merge                                                                                                                                                                                │
│ - 0.4–0.7 → Review queue                                                                                                                                                                            │
│ - < 0.4 → Skip                                                                                                                                                                                      │
│                                                                                                                                                                                                     │
│ Files                                                                                                                                                                                               │
│                                                                                                                                                                                                     │
│ ┌─────────────────────────────────────┬──────────────────────────────────────────────────────────────────────────────────┐                                                                          │
│ │                File                 │                                      Change                                      │                                                                          │
│ ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────┤                                                                          │
│ │ sql/schema.sql                      │ Add merge_candidate table + merged_into_id column on developer_profile           │                                                                          │
│ ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────┤                                                                          │
│ │ app/ingest/bridge/resolver.py       │ NEW — IdentityResolver with blocking, scoring, Jaro-Winkler, merge orchestration │                                                                          │
│ ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────┤                                                                          │
│ │ app/ingest/bridge/storage.py        │ Add merge_profiles() method (FK cascade, soft-delete source)                     │                                                                          │
│ ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────┤                                                                          │
│ │ app/common/enum/ingest.py           │ Add IDENTITY_RESOLVE to IngestJobType                                            │                                                                          │
│ ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────┤                                                                          │
│ │ app/ingest/pipeline/steps.py        │ Insert identity_resolve step into DAILY_STEPS + DEPENDENT_STEPS                  │                                                                          │
│ ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────┤                                                                          │
│ │ app/ingest/pipeline/runner.py       │ Add _step_identity_resolve dispatch + handler                                    │                                                                          │
│ ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────┤                                                                          │
│ │ app/ingest/cli.py                   │ Add identity-resolve CLI command                                                 │                                                                          │
│ ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────┤                                                                          │
│ │ app/api/v1/controller/ingest_api.py │ Add 6 review queue API endpoints                                                 │                                                                          │
│ └─────────────────────────────────────┴──────────────────────────────────────────────────────────────────────────────────┘                                                                          │
│                                                                                                                                                                                                     │
│ 1. Schema — sql/schema.sql                                                                                                                                                                          │
│                                                                                                                                                                                                     │
│ CREATE TABLE IF NOT EXISTS merge_candidate (                                                                                                                                                        │
│     id                  TEXT PRIMARY KEY DEFAULT 'mc_' || gen_random_uuid(),                                                                                                                        │
│     source_profile_id   TEXT NOT NULL REFERENCES developer_profile(id),                                                                                                                             │
│     target_profile_id   TEXT NOT NULL REFERENCES developer_profile(id),                                                                                                                             │
│     confidence_score    NUMERIC(5,4) NOT NULL,                                                                                                                                                      │
│     signals             JSONB NOT NULL DEFAULT '[]'::jsonb,                                                                                                                                         │
│     status              VARCHAR(30) NOT NULL DEFAULT 'pending',                                                                                                                                     │
│     resolved_profile_id TEXT,                                                                                                                                                                       │
│     reviewed_by         TEXT,                                                                                                                                                                       │
│     reviewed_at         TIMESTAMPTZ,                                                                                                                                                                │
│     merged_at           TIMESTAMPTZ,                                                                                                                                                                │
│     is_deleted          BOOLEAN DEFAULT FALSE NOT NULL,                                                                                                                                             │
│     created_at          TIMESTAMPTZ DEFAULT NOW() NOT NULL,                                                                                                                                         │
│     updated_at          TIMESTAMPTZ DEFAULT NOW() NOT NULL,                                                                                                                                         │
│     CONSTRAINT mc_unique_pair UNIQUE (source_profile_id, target_profile_id)                                                                                                                         │
│ );                                                                                                                                                                                                  │
│                                                                                                                                                                                                     │
│ Idempotent migration: ALTER TABLE developer_profile ADD COLUMN IF NOT EXISTS merged_into_id TEXT;                                                                                                   │
│                                                                                                                                                                                                     │
│ 2. Core Resolver — NEW app/ingest/bridge/resolver.py                                                                                                                                                │
│                                                                                                                                                                                                     │
│ IdentityResolver(pool) with async run(since_hours, full_scan) -> ResolverStats                                                                                                                      │
│                                                                                                                                                                                                     │
│ Blocking (avoids O(n²))                                                                                                                                                                             │
│                                                                                                                                                                                                     │
│ Only compare profiles within blocks that share a potential signal:                                                                                                                                  │
│ 1. Email block — group by normalized gh_users.email / developer_profile.email_hint                                                                                                                  │
│ 2. Cross-ref block — hf_users.github_username points to GH login owned by a different developer_profile                                                                                             │
│ 3. Social handle block — group by normalized Twitter handle across gh_users.twitter / hf_users.twitter                                                                                              │
│ 4. Name block — group by normalized name (lowercase, strip diacritics), cap 50 per block                                                                                                            │
│ 5. LinkedIn URL block — profiles linked to same ln_pending_urls.linkedin_url                                                                                                                        │
│                                                                                                                                                                                                     │
│ Preloading                                                                                                                                                                                          │
│                                                                                                                                                                                                     │
│ Single query: developer_profile LEFT JOIN gh_users LEFT JOIN hf_users LEFT JOIN ln_pending_urls → ProfileData dataclass for all candidate profiles. No N+1.                                         │
│                                                                                                                                                                                                     │
│ Scoring                                                                                                                                                                                             │
│                                                                                                                                                                                                     │
│ For each pair in a block, compute all applicable signals. Score = max(weights).                                                                                                                     │
│                                                                                                                                                                                                     │
│ Triage                                                                                                                                                                                              │
│                                                                                                                                                                                                     │
│ - ≥ 0.7 → merge_candidate(status='approved') + execute merge immediately                                                                                                                            │
│ - 0.4–0.7 → merge_candidate(status='pending')                                                                                                                                                       │
│ - Canonical ordering: older ID = target, newer = source. Skip if pair already merged.                                                                                                               │
│                                                                                                                                                                                                     │
│ Jaro-Winkler                                                                                                                                                                                        │
│                                                                                                                                                                                                     │
│ Pure Python implementation (~35 lines). No external dependency — blocks are small (2–10 profiles).                                                                                                  │
│                                                                                                                                                                                                     │
│ 3. Merge Execution — storage.py → merge_profiles()                                                                                                                                                  │
│                                                                                                                                                                                                     │
│ Single transaction:                                                                                                                                                                                 │
│ 1. Copy non-null platform links source → target (e.g., HF username)                                                                                                                                 │
│ 2. Handle UNIQUE FK tables (social_profile, aggregated_individual_profile, cohesive_individual_profile): if target has row → delete source's row; else re-point                                     │
│ 3. Re-point non-unique FKs: campaign_recipient, merge_audit_log                                                                                                                                     │
│ 4. Soft-delete source: is_deleted=TRUE, merged_into_id=target_dp_id                                                                                                                                 │
│ 5. Update merge_candidate: status='merged', merged_at=NOW()                                                                                                                                         │
│ 6. Mark target: ingestion_status='pending' (triggers rebuild in bridge_sync)                                                                                                                        │
│                                                                                                                                                                                                     │
│ 4. Pipeline Integration                                                                                                                                                                             │
│                                                                                                                                                                                                     │
│ steps.py                                                                                                                                                                                            │
│                                                                                                                                                                                                     │
│ - DAILY_STEPS: insert identity_resolve after hf_ingest, before bridge_sync                                                                                                                          │
│ - DEPENDENT_STEPS: insert identity_resolve after hf_ingest, before ln_crossref                                                                                                                      │
│                                                                                                                                                                                                     │
│ runner.py                                                                                                                                                                                           │
│                                                                                                                                                                                                     │
│ - Add "identity_resolve": self._step_identity_resolve to dispatch                                                                                                                                   │
│ - Handler: IdentityResolver(self._pool).run(since_hours=params.get("since_hours", 24))                                                                                                              │
│                                                                                                                                                                                                     │
│ enums                                                                                                                                                                                               │
│                                                                                                                                                                                                     │
│ - Add IDENTITY_RESOLVE = "identity_resolve" to IngestJobType                                                                                                                                        │
│                                                                                                                                                                                                     │
│ 5. CLI                                                                                                                                                                                              │
│                                                                                                                                                                                                     │
│ python -m app.ingest.cli identity-resolve --since-hours 24 --full-scan                                                                                                                              │
│                                                                                                                                                                                                     │
│ 6. API Endpoints                                                                                                                                                                                    │
│                                                                                                                                                                                                     │
│ ┌────────┬──────────────────────────────────────────┬─────────────────────────────────────────────────┐                                                                                             │
│ │ Method │                   Path                   │                   Description                   │                                                                                             │
│ ├────────┼──────────────────────────────────────────┼─────────────────────────────────────────────────┤                                                                                             │
│ │ GET    │ /ingest/identity/candidates              │ List (filter: status, min_score, limit, offset) │                                                                                             │
│ ├────────┼──────────────────────────────────────────┼─────────────────────────────────────────────────┤                                                                                             │
│ │ GET    │ /ingest/identity/candidates/{id}         │ Detail with profile previews + signals          │                                                                                             │
│ ├────────┼──────────────────────────────────────────┼─────────────────────────────────────────────────┤                                                                                             │
│ │ POST   │ /ingest/identity/candidates/{id}/approve │ Approve + execute merge                         │                                                                                             │
│ ├────────┼──────────────────────────────────────────┼─────────────────────────────────────────────────┤                                                                                             │
│ │ POST   │ /ingest/identity/candidates/{id}/reject  │ Reject                                          │                                                                                             │
│ ├────────┼──────────────────────────────────────────┼─────────────────────────────────────────────────┤                                                                                             │
│ │ POST   │ /ingest/identity/resolve                 │ Trigger as background task                      │                                                                                             │
│ ├────────┼──────────────────────────────────────────┼─────────────────────────────────────────────────┤                                                                                             │
│ │ GET    │ /ingest/identity/stats                   │ Counts by status, avg scores                    │                                                                                             │
│ └────────┴──────────────────────────────────────────┴─────────────────────────────────────────────────┘                                                                                             │
│                                                                                                                                                                                                     │
│ Implementation Order                                                                                                                                                                                │
│                                                                                                                                                                                                     │
│ 1. Schema (merge_candidate + merged_into_id)                                                                                                                                                        │
│ 2. Core resolver (resolver.py — blocking, scoring, Jaro-Winkler)                                                                                                                                    │
│ 3. Merge execution (storage.py — merge_profiles)                                                                                                                                                    │
│ 4. Enum (IDENTITY_RESOLVE)                                                                                                                                                                          │
│ 5. Pipeline integration (steps.py + runner.py)                                                                                                                                                      │
│ 6. CLI command                                                                                                                                                                                      │
│ 7. API endpoints (6 review queue)                                                                                                                                                                   │
│ 8. Lint + test                                                                                                                                                                                      │
│                                                                                                                                                                                                     │
│ Verification                                                                                                                                                                                        │
│                                                                                                                                                                                                     │
│ 1. make lint — no new errors                                                                                                                                                                        │
│ 2. CLI: python -m app.ingest.cli identity-resolve --since-hours 168 — finds/resolves candidates                                                                                                     │
│ 3. API: GET /ingest/identity/candidates?status=pending — returns review queue                                                                                                                       │
│ 4. API: POST /ingest/identity/candidates/{id}/approve — merges, cascades FKs                                                                                                                        │
│ 5. Pipeline: POST /ingest/pipeline/start {"pipeline_type": "dependent"} — identity_resolve runs between hf_ingest and ln_crossref                                                                   │
│ 6. Merged profile: source has is_deleted=TRUE, merged_into_id set; target has updated links                                                                                                         │
│ 7. Bridge sync rebuilds downstream tables for merged profile                                                                                                                                        │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

