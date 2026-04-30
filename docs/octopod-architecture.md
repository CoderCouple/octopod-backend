 Octopod Backend — Complete Codebase Overview
                                                                                                                                                                                                       
  High-Level Architecture

  ┌────────────────────────────────────────────────────────────────────┐
  │                        FastAPI Application                         │
  │                         (app/main.py)                              │
  ├─────────────┬──────────────┬──────────────┬────────────────────────┤
  │  Middleware │   API Layer  │   Services   │   Background Tasks     │
  │  ─────────  │   ─────────  │   ────────   │   ────────────────     │
  │  • Auth     │  /api/v1/*   │  • Search    │  • Ingestion jobs      │
  │  • CORS     │  33 ingest   │  • Profile   │  • Pipeline steps      │
  │  • Logging  │  14 email    │  • Email     │  • Bridge sync         │
  │             │  5 profile   │  • Ranking   │  • Identity resolution │
  │             │  2 health    │              │  • Embedding           │
  └─────────────┴──────────────┴──────────────┴────────────────────────┘
           │                    │              │               
      ┌────▼────┐          ┌────▼────┐   ┌─────▼─────┐
      │PostgreSQL│         │ Qdrant  │   │OpenSearch │
      │ (asyncpg)│         │(vectors)│   │ (keyword) │
      └─────────┘          └─────────┘   └───────────┘

  Database Layer (PostgreSQL + Qdrant + OpenSearch)

  ┌── PostgreSQL  ──────────────────────────────────────────────────────┐
  │                                                                     │
  │  Raw Ingestion Tables          Bridge/Profile Tables                │
  │  ────────────────────          ─────────────────────                │
  │  • gh_users                    • developer_profile                  │
  │  • gh_repos                    • merge_candidate                    │
  │  • gh_contributions            • profile_embedding                  │
  │  • hf_users                                                         │
  │  • hf_models                   Job Tracking Tables                  │
  │  • hf_datasets                 ───────────────────                  │
  │  • ln_profiles                 • ingest_job                         │
  │                                • ingest_job_item                    │
  │  Email Tables                  • pipeline_execution                 │
  │  ────────────                  • pipeline_step_execution            │
  │  • mailbox                     • pipeline_schedule                  │
  │  • email_template              • checkpoint                         │
  │  • email_campaign                                                   │
  │  • email_campaign_step         Search Tables                        │
  │  • email_recipient             ────────────                         │
  │  • email_send_log              • search_log                         │
  │  • email_event                 • ranking_score                      │
  │                                                                     │
  └─────────────────────────────────────────────────────────────────────┘

  ┌── Qdrant  ──────────────────────────────────────┐
  │  Collection: developer_profiles                 │
  │  • 384-dim vectors (MiniLM-L6-v2)               │
  │  • payload: embedding_text + meta               │
  └─────────────────────────────────────────────────┘

  ┌── OpenSearch  ──────────────────────────────────────────────────────┐
  │  Index: developer_profiles                                          │
  │  • Full-text search on bio, skills, repos, contributions            │
  └─────────────────────────────────────────────────────────────────────┘

  Request Flow

  Client Request
        │
        ▼
  ┌─────────────┐
  │  Middleware │──► CORS ──► Auth (API key check) ──► Logging
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐     ┌──────────────────────────────────┐
  │  Router     │────►│  app/api/v1/router.py            │
  │  /api/v1    │     │  Includes all controller routers │
  └──────┬──────┘     └──────────────────────────────────┘
         │
         ├──► /ingest/*      → 5 ingest controllers (33 endpoints)
         ├──► /email/*       → 5 email controllers (14 endpoints)
         ├──► /developers/*  → profile + search (5 endpoints)
         └──► /health, /ready → health checks
                │
                ▼
  ┌──────────────────┐     ┌──────────────┐
  │  Request Model   │────►│  Controller  │
  │  (Pydantic)      │     │  (endpoint)  │
  └──────────────────┘     └──────┬───────┘
                                  │
                      ┌───────────┴───────────┐
                      │                       │
                Sync Response          Background Task
                (immediate)            (job_id returned)
                      │                       │
                      ▼                       ▼
             ┌──────────────┐      ┌──────────────────┐
             │BaseResponse[T]│      │ asyncio.run(...)  │
             │{success,data} │      │ w/ JobTracker     │
             └──────────────┘      └──────────────────┘

  Ingestion Pipeline — The Core Flow

                      ┌─────────────────────┐
                      │   API Trigger        │
                      │ POST /ingest/gh/run  │
                      │ POST /ingest/hf/run  │
                      │ POST /ingest/ln/run  │
                      └──────────┬──────────┘
                                 │
                                 ▼
                      ┌─────────────────────┐
                      │   Job Created        │
                      │   (ingest_job table) │
                      │   Status: pending    │
                      └──────────┬──────────┘
                                 │
                      ┌──────────▼──────────┐
                      │   BackgroundTask     │
                      │   launched           │
                      └──────────┬──────────┘
                                 │
                ┌────────────────┼────────────────┐
                ▼                ▼                 ▼
      ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
      │  GH Pipeline │  │  HF Pipeline │  │  LN Pipeline │
      └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
             │                 │                  │
             ▼                 ▼                  ▼
      ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
      │ Orchestrator │  │ Orchestrator │  │ Orchestrator │
      │ (semaphore   │  │ (semaphore   │  │ (Proxycurl   │
      │  concurrency)│  │  concurrency)│  │  API client) │
      └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
             │                 │                  │
             ▼                 ▼                  ▼
      ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
      │ API Client   │  │ API Client   │  │ Proxycurl    │
      │ (GitHub REST │  │ (HF Hub API) │  │ Client       │
      │  + GraphQL)  │  │              │  │              │
      └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
             │                 │                  │
             ▼                 ▼                  ▼
      ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
      │   Storage    │  │   Storage    │  │   Storage    │
      │ (PostgreSQL) │  │ (PostgreSQL) │  │ (PostgreSQL) │
      │              │  │              │  │              │
      └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
             │                 │                  │
             └────────────┬────┘──────────────────┘
                          │
                          ▼
               ┌─────────────────────┐
               │   Checkpoint        │
               │   (platform, login, │
               │    stage, status)   │
               └─────────────────────┘

  GitHub Ingestion Detail

  POST /ingest/gh/discover                 POST /ingest/gh/run
          │                                        │
          ▼                                        ▼
  ┌───────────────┐                      ┌──────────────────┐
  │ GHDiscover    │                      │ GHOrchestrator   │
  │ • Search API  │                      │ • Semaphore(N)   │
  │ • star-based  │                      │ • Per-user tasks │
  │   ranges      │                      └────────┬─────────┘
  │ • Saves to    │                               │
  │   checkpoint  │                    Per user (concurrent):
  └───────────────┘                               │
                                      ┌───────────┼───────────┐
                                      ▼           ▼           ▼
                                 ┌─────────┐ ┌────────┐ ┌─────────┐
                                 │ Profile │ │ Repos  │ │Contribs │
                                 │ fetch   │ │ fetch  │ │ fetch   │
                                 └────┬────┘ └───┬────┘ └────┬────┘
                                      │          │           │
                                      └──────────┼───────────┘
                                                 ▼
                                      ┌─────────────────────┐
                                      │  GHStorage           │
                                      │  • UPSERT gh_users   │
                                      │  • UPSERT gh_repos   │
                                      │  • INSERT gh_contribs│
                                      │  • SAVE gh_readmes   │
                                      └─────────────────────┘

  Bridge Sync Pipeline (Raw → Unified Profile)

  ┌─────────────────────────────────────────────────────────────────────┐
  │                    POST /ingest/sync                                 │
  │                    POST /ingest/pipeline/start                       │
  └──────────────────────────┬──────────────────────────────────────────┘
                             │
                             ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                    Bridge Sync Pipeline                               │
  │                    (4-Layer Merge Architecture)                       │
  │                                                                      │
  │  Layer 1: RAW EXTRACTION                                             │
  │  ┌──────────┐  ┌───────────┐  ┌──────────┐                         │
  │  │ gh_users │  │ hf_users  │  │ln_profiles│                         │
  │  │ gh_repos │  │ hf_models │  │          │                          │
  │  │ gh_contri│  │ hf_dataset│  │          │                          │
  │  └────┬─────┘  └─────┬─────┘  └────┬─────┘                         │
  │       │              │              │                                │
  │       ▼              ▼              ▼                                │
  │  Layer 2: DOMAIN PROFILES                                            │
  │  ┌──────────────────────────────────────┐                           │
  │  │  BridgeSync.sync_profiles()          │                           │
  │  │  • For each raw user:                │                           │
  │  │    - Find/create developer_profile   │                           │
  │  │    - Match by email → username → name│                           │
  │  │    - Aggregate repos, stars, models  │                           │
  │  │    - Compute skills from repos/models│                           │
  │  └──────────────────┬───────────────────┘                           │
  │                     │                                                │
  │                     ▼                                                │
  │  Layer 3: UNIFIED PROFILE                                            │
  │  ┌──────────────────────────────────────┐                           │
  │  │  developer_profile table             │                           │
  │  │  • github_username                   │                           │
  │  │  • huggingface_username              │                           │
  │  │  • display_name, email, company      │                           │
  │  │  • total_repos, total_stars          │                           │
  │  │  • total_hf_models, total_hf_dls    │                           │
  │  │  • top_languages (JSONB)             │                           │
  │  │  • embedding_text (generated)        │                           │
  │  └──────────────────┬───────────────────┘                           │
  │                     │                                                │
  │                     ▼                                                │
  │  Layer 4: SEARCH INDEX                                               │
  │  ┌──────────────────────────────────────┐                           │
  │  │  DualIndexer                         │                           │
  │  │  • Qdrant: 384-dim vector embedding  │                           │
  │  │  • OpenSearch: full-text document    │                           │
  │  │  Both indexed in parallel            │                           │
  │  └──────────────────────────────────────┘                           │
  │                                                                      │
  └─────────────────────────────────────────────────────────────────────┘

  Identity Resolution

  POST /ingest/identity/resolve
          │
          ▼
  ┌───────────────────────────────────────┐
  │  IdentityResolver.run()               │
  │                                       │
  │  Step 1: Build Blocking Pairs         │
  │  ┌───────────────────────────────┐    │
  │  │ Group profiles by:            │    │
  │  │ • Shared email domain         │    │
  │  │ • Similar display names       │    │
  │  │ • Overlapping organizations   │    │
  │  │ → Candidate pairs             │    │
  │  └──────────────┬────────────────┘    │
  │                 │                      │
  │  Step 2: Score Each Pair              │
  │  ┌──────────────▼────────────────┐    │
  │  │ Signal scoring (0-1):         │    │
  │  │ • Email match      (0.4)      │    │
  │  │ • Name similarity  (0.25)     │    │
  │  │ • Company match    (0.15)     │    │
  │  │ • Location match   (0.1)      │    │
  │  │ • Avatar match     (0.1)      │    │
  │  │ → confidence_score            │    │
  │  └──────────────┬────────────────┘    │
  │                 │                      │
  │  Step 3: Decide                       │
  │  ┌──────────────▼────────────────┐    │
  │  │ score >= 0.85 → AUTO-MERGE    │    │
  │  │ score >= 0.50 → PENDING review│    │
  │  │ score <  0.50 → SKIP          │    │
  │  └──────────────┬────────────────┘    │
  │                 │                      │
  │                 ▼                      │
  │  ┌───────────────────────────────┐    │
  │  │ merge_candidate table         │    │
  │  │ Status: pending | merged |    │    │
  │  │         approved | rejected   │    │
  │  └───────────────────────────────┘    │
  └───────────────────────────────────────┘

  Manual Review Flow:
  GET  /identity/candidates          → List candidates
  GET  /identity/candidates/{id}     → Detail + both profiles
  POST /identity/candidates/{id}/approve → Merge profiles
  POST /identity/candidates/{id}/reject  → Reject match

  Pipeline Orchestration System

  POST /ingest/pipeline/start
       { pipeline_type: "full_github" | "full_huggingface" | "full" | ... }
          │
          ▼
  ┌───────────────────────────────────────────────────────┐
  │  PipelineRunner                                        │
  │                                                        │
  │  pipeline_execution table (tracks overall run)         │
  │  pipeline_step_execution table (tracks each step)      │
  │                                                        │
  │  Full Pipeline Steps:                                  │
  │  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐       │
  │  │Step1│─►│Step2│─►│Step3│─►│Step4│─►│Step5│        │
  │  │Disc.│  │Ingest│ │Sync │  │Ident│  │Embed│        │
  │  └─────┘  └─────┘  └─────┘  └─────┘  └─────┘       │
  │                                                        │
  │  Control Signals:                                      │
  │  • PAUSE  → stops after current step completes         │
  │  • RESUME → continues from paused step                 │
  │  • CANCEL → marks execution as cancelled               │
  │  • RERUN  → creates new execution copying config       │
  │                                                        │
  │  Pipeline Types:                                       │
  │  • full_github    = discover → ingest → sync → embed   │
  │  • full_huggingface = discover → ingest → sync → embed │
  │  • full           = both platforms end-to-end           │
  │  • sync_only      = bridge sync only                   │
  │  • embed_only     = embedding generation only          │
  │  • identity_only  = identity resolution only           │
  └───────────────────────────────────────────────────────┘

  Developer Search Flow

  GET /developers/search?q="machine learning Python"
          │
          ▼
  ┌───────────────────────────────────────────────────────┐
  │  SearchService                                         │
  │                                                        │
  │  ┌─────────────────────┐  ┌─────────────────────┐    │
  │  │  Qdrant Vector      │  │  OpenSearch Keyword  │    │
  │  │  Search             │  │  Search              │    │
  │  │                     │  │                      │    │
  │  │  query → embed      │  │  query → BM25        │    │
  │  │  → cosine similarity│  │  → full-text match   │    │
  │  │  → top K results    │  │  → top K results     │    │
  │  └──────────┬──────────┘  └──────────┬───────────┘    │
  │             │                        │                 │
  │             └────────┬───────────────┘                 │
  │                      ▼                                 │
  │  ┌─────────────────────────────────────────────┐      │
  │  │  Reciprocal Rank Fusion (RRF)               │      │
  │  │                                              │      │
  │  │  For each result in both lists:              │      │
  │  │  score = Σ 1/(k + rank_i)                   │      │
  │  │  where k = 60 (constant)                    │      │
  │  │                                              │      │
  │  │  Merges both result sets by fused score      │      │
  │  └──────────────────┬──────────────────────────┘      │
  │                     │                                  │
  │                     ▼                                  │
  │  ┌─────────────────────────────────────────────┐      │
  │  │  Cross-Encoder Reranking (optional)         │      │
  │  │  • Takes top N fused results                │      │
  │  │  • Scores (query, profile_text) pairs       │      │
  │  │  • Re-sorts by cross-encoder score          │      │
  │  └──────────────────┬──────────────────────────┘      │
  │                     │                                  │
  │                     ▼                                  │
  │  ┌─────────────────────────────────────────────┐      │
  │  │  Return ranked developer profiles           │      │
  │  └─────────────────────────────────────────────┘      │
  └───────────────────────────────────────────────────────┘

  Email Outreach System

  ┌─────────────────────────────────────────────────────────────────────┐
  │                     Email Outreach Flow                               │
  │                                                                      │
  │  1. SETUP                                                            │
  │  ┌──────────────┐  ┌──────────────────┐  ┌────────────────┐        │
  │  │ Mailbox      │  │ Email Template   │  │ Campaign       │        │
  │  │ (OAuth creds)│  │ (Jinja2 body,    │  │ (multi-step    │        │
  │  │ IMAP/SMTP    │  │  subject, vars)  │  │  sequences)    │        │
  │  └──────┬───────┘  └────────┬─────────┘  └───────┬────────┘        │
  │         │                   │                     │                  │
  │  2. CAMPAIGN CONFIGURATION                                           │
  │  ┌──────▼───────────────────▼─────────────────────▼────────┐        │
  │  │  Campaign Steps                                          │        │
  │  │  ┌────────┐    ┌────────┐    ┌────────┐                │        │
  │  │  │ Step 1 │───►│ Step 2 │───►│ Step 3 │                │        │
  │  │  │Day 0   │    │Day 3   │    │Day 7   │                │        │
  │  │  │Template │    │Template│    │Template│                │        │
  │  │  │   A    │    │   B    │    │   C    │                │        │
  │  │  └────────┘    └────────┘    └────────┘                │        │
  │  └─────────────────────────┬────────────────────────────────┘        │
  │                            │                                         │
  │  3. RECIPIENTS                                                       │
  │  ┌─────────────────────────▼────────────────────────────────┐        │
  │  │  email_recipient table                                    │        │
  │  │  • developer_profile_id → enriched email                 │        │
  │  │  • status: pending → sent → replied | bounced           │        │
  │  │  • current_step tracking                                 │        │
  │  └─────────────────────────┬────────────────────────────────┘        │
  │                            │                                         │
  │  4. SENDING                                                          │
  │  ┌─────────────────────────▼────────────────────────────────┐        │
  │  │  EmailSender                                              │        │
  │  │  • Render template with recipient vars                   │        │
  │  │  • Inject tracking pixel (1x1 transparent PNG)           │        │
  │  │  • Send via SMTP through mailbox                         │        │
  │  │  • Log to email_send_log                                 │        │
  │  └─────────────────────────┬────────────────────────────────┘        │
  │                            │                                         │
  │  5. TRACKING                                                         │
  │  ┌─────────────────────────▼────────────────────────────────┐        │
  │  │  Events tracked:                                          │        │
  │  │  • open (tracking pixel loaded)                          │        │
  │  │  • click (redirect link clicked)                         │        │
  │  │  • reply (IMAP inbox check)                              │        │
  │  │  • bounce (delivery failure)                             │        │
  │  │  → email_event table                                     │        │
  │  └──────────────────────────────────────────────────────────┘        │
  │                                                                      │
  └─────────────────────────────────────────────────────────────────────┘

  Embedding Generation Flow

  POST /ingest/embed
          │
          ▼
  ┌───────────────────────────────────────────────┐
  │  BatchEmbedder                                 │
  │                                                │
  │  1. Query profiles needing embeddings          │
  │     (new or updated since last embed)          │
  │                                                │
  │  2. For each profile:                          │
  │     ┌────────────────────────────────────┐     │
  │     │ Build embedding_text:              │     │
  │     │ "{name} | {bio} | Skills: {langs} │     │
  │     │  | Repos: {top_repos} | {company} │     │
  │     │  | {location}"                     │     │
  │     └──────────────┬─────────────────────┘     │
  │                    │                           │
  │  3. Batch encode   │                           │
  │     ┌──────────────▼─────────────────────┐     │
  │     │ SentenceTransformer                │     │
  │     │ model: all-MiniLM-L6-v2           │     │
  │     │ → 384-dimensional vectors          │     │
  │     └──────────────┬─────────────────────┘     │
  │                    │                           │
  │  4. Dual index     │                           │
  │     ┌──────────────▼─────────────────────┐     │
  │     │ DualIndexer                        │     │
  │     │ ├─► Qdrant: upsert vector + payload│     │
  │     │ └─► OpenSearch: index document     │     │
  │     └────────────────────────────────────┘     │
  └───────────────────────────────────────────────┘

  API Endpoint Map (54 total)

  /api/v1/
  ├── health/
  │   ├── GET  /health              → liveness check
  │   └── GET  /ready               → readiness check
  │
  ├── ingest/                        (33 endpoints — 5 controllers)
  │   ├── source/
  │   │   ├── POST /gh/discover     → discover GitHub users
  │   │   ├── POST /gh/run          → ingest GitHub profiles
  │   │   ├── POST /hf/discover     → discover HuggingFace authors
  │   │   ├── POST /hf/run          → ingest HuggingFace profiles
  │   │   ├── POST /ln/discover     → extract LinkedIn URLs
  │   │   └── POST /ln/run          → ingest LinkedIn profiles
  │   │
  │   ├── jobs/
  │   │   ├── GET  /status          → checkpoint summary
  │   │   ├── POST /retry           → retry failed items
  │   │   ├── GET  /jobs            → list jobs (filterable)
  │   │   ├── GET  /jobs/{id}       → job detail + counts
  │   │   ├── GET  /jobs/{id}/items → job item list
  │   │   ├── GET  /jobs/{id}/data  → ingested data for job
  │   │   └── GET  /jobs/{id}/data/{login} → single user data
  │   │
  │   ├── pipeline/
  │   │   ├── POST /sync            → trigger bridge sync
  │   │   ├── POST /embed           → trigger batch embedding
  │   │   ├── POST /pipeline/start  → start pipeline
  │   │   ├── GET  /pipeline/active → list active pipelines
  │   │   ├── GET  /pipeline/{id}   → execution detail
  │   │   ├── POST /pipeline/{id}/pause
  │   │   ├── POST /pipeline/{id}/resume
  │   │   ├── POST /pipeline/{id}/cancel
  │   │   ├── POST /pipeline/{id}/rerun
  │   │   └── GET  /pipeline/status → health dashboard
  │   │
  │   ├── schedule/
  │   │   ├── POST /schedule        → create schedule
  │   │   ├── GET  /schedules       → list schedules
  │   │   ├── PUT  /schedule/{id}   → update schedule
  │   │   └── DELETE /schedule/{id} → delete schedule
  │   │
  │   └── identity/
  │       ├── GET  /identity/candidates
  │       ├── GET  /identity/candidates/{id}
  │       ├── POST /identity/candidates/{id}/approve
  │       ├── POST /identity/candidates/{id}/reject
  │       ├── POST /identity/resolve
  │       └── GET  /identity/stats
  │
  ├── email/                         (14 endpoints — 5 controllers)
  │   ├── mailbox/     → CRUD + OAuth connect
  │   ├── templates/   → CRUD + preview
  │   ├── campaigns/   → CRUD + steps + recipients + send
  │   ├── tracking/    → pixel + click + events
  │   └── enrichment/  → find emails for profiles
  │
  └── developers/                    (5 endpoints)
      ├── GET  /search              → hybrid search
      ├── GET  /{id}                → profile detail
      ├── GET  /{id}/repos          → repos list
      ├── GET  /{id}/contributions  → contribution history
      └── GET  /rankings            → ranked leaderboard

  File Structure (Controller Layer)

  app/api/v1/
  ├── controller/
  │   ├── ingest_source_api.py      ← GH/HF/LN discover + run
  │   ├── ingest_job_api.py         ← Job monitoring + retry
  │   ├── ingest_pipeline_api.py    ← Pipeline orchestration
  │   ├── ingest_schedule_api.py    ← Schedule CRUD
  │   ├── ingest_identity_api.py    ← Identity resolution
  │   ├── mailbox_api.py            ← Mailbox management
  │   ├── email_campaign_api.py     ← Campaign management
  │   ├── email_template_api.py     ← Template CRUD
  │   ├── email_tracking_api.py     ← Open/click tracking
  │   ├── email_enrichment_api.py   ← Email discovery
  │   └── developer_api.py          ← Search + profiles
  ├── request/
  │   ├── ingest_request.py         ← 10 request models
  │   └── email_request.py          ← Email request models
  ├── response/
  │   ├── base_response.py          ← BaseResponse[T] wrapper
  │   ├── ingest_response.py        ← 18 response models
  │   └── email_response.py         ← Email response models
  └── router.py                     ← Registers all routers

  Key Service Layer

  app/
  ├── ingest/
  │   ├── github/
  │   │   ├── config.py             ← GH-specific settings
  │   │   ├── client.py             ← GitHub API client (REST + GraphQL)
  │   │   ├── discover.py           ← Star-range based discovery
  │   │   ├── orchestrator.py       ← Concurrent user ingestion
  │   │   ├── storage.py            ← PostgreSQL writes
  │   │   └── token_pool.py         ← Rotating GitHub PATs
  │   ├── huggingface/
  │   │   ├── config.py / client.py / discover.py
  │   │   ├── orchestrator.py / storage.py
  │   ├── linkedin/
  │   │   ├── config.py / client.py (Proxycurl)
  │   │   ├── discover.py / orchestrator.py / storage.py
  │   ├── bridge/
  │   │   ├── sync.py               ← 4-layer merge pipeline
  │   │   ├── resolver.py           ← Identity resolution engine
  │   │   ├── storage.py            ← Profile merge operations
  │   │   └── indexer.py            ← DualIndexer (Qdrant + OpenSearch)
  │   ├── pipeline/
  │   │   ├── runner.py             ← Step-based pipeline executor
  │   │   ├── tracker.py            ← Execution state tracking
  │   │   └── scheduler.py          ← Cron-based scheduling
  │   └── common/
  │       ├── job_tracker.py        ← Job lifecycle management
  │       └── embed.py              ← Batch embedding generation
  ├── service/
  │   ├── search_service.py         ← Hybrid search + RRF + reranking
  │   ├── profile_service.py        ← Profile CRUD
  │   └── ranking_service.py        ← Developer ranking/scoring
  └── common/
      └── ingest_common.py          ← Shared helpers

  That's the full codebase architecture. The system is essentially a developer intelligence platform — it discovers developers across GitHub, HuggingFace, and LinkedIn, merges cross-platform
  identities, builds searchable profiles with vector + keyword indexing, and enables outreach via email campaigns.
