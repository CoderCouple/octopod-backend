Ingestion Pipeline — Architecture & State Diagram

  High-Level Data Flow

  ┌─────────────────────────────────────────────────────────────────────┐
  │                        DISCOVERY PHASE                              │
  │                                                                     │
  │  ┌──────────────────────┐       ┌──────────────────────┐            │
  │  │   GH Discover        │       │   HF Discover        │            │
  │  │                      │       │                      │            │
  │  │ Follower bands ──┐   │       │ Top models by ──┐    │            │
  │  │ (12 strata)      │   │       │ downloads       │    │            │
  │  │                   ▼  │       │                 ▼    │            │
  │  │ Star-based     MERGE │       │ Top models by MERGE  │            │
  │  │ repo owners ──► +RANK│       │ likes ────────►+RANK │            │
  │  │                   │  │       │                 │    │            │
  │  │                   ▼  │       │                 ▼    │            │
  │  │   logins.txt (5k)    │       │  usernames.txt (5k)  │            │
  │  └──────────────────────┘       └──────────────────────┘            │
  └─────────────────────────────────────────────────────────────────────┘
                      │                           │
                      ▼                           ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                       INGESTION PHASE                                │
  │                                                                      │
  │  ┌──────────┐    ┌────────────┐     ┌──────────────────────────┐     │
  │  │ Producer │───►│   Queue    │───► │  Worker Pool (N=8)       │     │
  │  │ (logins) │    │ (bounded)  │     │                          │     │
  │  └──────────┘    └────────────┘     │  Worker 0 ──► _process() │     │
  │                                     │  Worker 1 ──► _process() │     │
  │                                     │  Worker 2 ──► _process() │     │
  │                                     │  ...                     │     │
  │                                     │  Worker 7 ──► _process() │     │
  │                                     └──────────────────────────┘     │
  │                                                 │                    │
  │                    ┌───────────────────────────┐│                    │
  │                    │      Token Pool           ││                    │
  │                    │  ┌───┐ ┌───┐ ┌───┐        ││                    │
  │                    │  │T1 │ │T2 │ │T3 │ ...    |│  ◄─── rate-limit   │
  │                    │  └───┘ └───┘ └───┘        ││     aware rotation │
  │                    └───────────────────────────┘│                    │
  │                                                 ▼                    │
  │                    ┌───────────────────────────────────┐             │
  │                    │         PostgreSQL                │             │
  │                    │  gh_users / hf_users              │             │
  │                    │  gh_repositories / hf_models      │             │
  │                    │  gh_commits / hf_datasets         │             │
  │                    │  gh_activity_events               │             │
  │                    │  gh_checkpoints / hf_checkpoints  │             │
  │                    └───────────────────────────────────┘             │
  └─────────────────────────────────────────────────────────────────────┘

  Per-User Processing Pipeline

  Each worker runs this for every login/username:

    ┌─────────────┐
    │ Pick from   │
    │   Queue     │
    └──────┬──────┘
           │
           ▼
    ┌─────────────────┐    YES    ┌──────────┐
    │ recently_ingested│─────────►│  SKIP    │
    │ (within 24h)?    │          │ stats++  │
    └────────┬─────────┘          └──────────┘
             │ NO
             ▼
    ┌─────────────────┐
    │ Fetch profile   │──── GitHub: GraphQL bundle (user+repos+commits)
    │ from API        │──── HF: REST /api/users/{u}/overview
    └────────┬────────┘
             │
       ┌─────┼──────────────┐
       │     │              │
       ▼     ▼              ▼
    ┌─────┐ ┌──────┐  ┌──────────┐
    │ OK  │ │Perm. │  │Transient │
    │     │ │Error │  │Error     │
    └──┬──┘ └──┬───┘  └────┬─────┘
       │       │            │
       │       ▼            ▼
       │  checkpoint     checkpoint
       │  "failed"       "pending"
       │  (don't retry)  (will retry)
       │
       ▼
    ┌──────────────┐
    │ Upsert user  │
    │ to Postgres  │
    └──────┬───────┘
           │
           ▼
    ┌──────────────────────────────┐
    │ Fetch related data           │
    │                              │
    │ GitHub:                      │
    │   upsert_repos()             │
    │   upsert_commits()           │
    │   fetch_events()(best-effort)│
    │   upsert_events()            │
    │                              │
    │ HuggingFace:                 │
    │   list_models() ─┐ parallel  │
    │   list_datasets()┘ gather    │
    │   upsert_models()            │
    │   upsert_datasets()          │
    └──────────┬───────────────────┘
               │
               ▼
    ┌──────────────────┐
    │ checkpoint       │
    │ "success"        │
    │ stats.succeeded++│
    └──────────────────┘

  Checkpoint State Machine

  The gh_checkpoints / hf_checkpoints tables track each user's ingestion state:

                      ┌───────────────────────────┐
                      │        NEW USER           │
                      │  (no checkpoint row yet)  │
                      └─────────────┬─────────────┘
                                    │
                      first attempt │
                                    ▼
                   ┌────────────────────────────────┐
             ┌─────│           PENDING              │ ◄────────┐
             │     │  (queued or transient failure) │          │
             │     └───────────┬──────────────────┬─┘          │
             │                 │                  │            │
             │     success     │                  │ transient  │
             │                 │                  │ error      │
             │                 ▼                  │            │
             │     ┌───────────────────┐          │            │
             │     │     SUCCESS       │          └────────────┘
             │     │                   │              (stays pending,
             │     │ last_success=NOW  │               attempt_count++)
             │     │ attempt_count++   │
             │     └───────────────────┘
             │
             │ permanent error
             │ (404, suspended, etc.)
             ▼
    ┌───────────────────┐
    │      FAILED       │
    │                   │
    │ last_error="..."  │
    │ attempt_count++   │
    └───────────────────┘

    Retry command: picks FAILED where attempt_count < max
    and re-queues them → back to PENDING

  State transitions summary:

  ┌─────────┬─────────────────────────────────────┬─────────┬─────────────────────────────────────────────────┐
  │  From   │                Event                │   To    │                      Notes                      │
  ├─────────┼─────────────────────────────────────┼─────────┼─────────────────────────────────────────────────┤
  │ (none)  │ First attempt starts                │ pending │ Row created                                     │
  ├─────────┼─────────────────────────────────────┼─────────┼─────────────────────────────────────────────────┤
  │ pending │ Ingestion succeeds                  │ success │ last_success = NOW()                            │
  ├─────────┼─────────────────────────────────────┼─────────┼─────────────────────────────────────────────────┤
  │ pending │ Transient error (5xx, timeout)      │ pending │ attempt_count++, last_error updated             │
  ├─────────┼─────────────────────────────────────┼─────────┼─────────────────────────────────────────────────┤
  │ pending │ Permanent error (404, 451)          │ failed  │ Won't auto-retry                                │
  ├─────────┼─────────────────────────────────────┼─────────┼─────────────────────────────────────────────────┤
  │ failed  │ Manual retry command                │ pending │ Re-queued for processing                        │
  ├─────────┼─────────────────────────────────────┼─────────┼─────────────────────────────────────────────────┤
  │ success │ Re-ingest after refresh_after_hours │ success │ recently_ingested() returns false, re-processes │
  └─────────┴─────────────────────────────────────┴─────────┴─────────────────────────────────────────────────┘

  Token Pool State Machine (GitHub)

    ┌──────────────┐
    │  Token Pool  │
    │  [T1, T2, T3]│
    └──────┬───────┘
           │
    Worker calls acquire()
           │
           ▼
    ┌───────────────────────────────────┐
    │ Pick token with highest           │
    │ remaining budget                  │
    │                                   │
    │ All exhausted? ──► Block on       │
    │                    Condition      │
    │                    (wait for      │
    │                     reset_at)     │
    └───────────────┬───────────────────┘
                    │
                    ▼
    ┌───────────────────────────────────┐
    │ Make API request                  │
    │ Read response headers:            │
    │   X-RateLimit-Remaining           │
    │   X-RateLimit-Reset               │
    └───────────────┬───────────────────┘
                    │
                    ▼
    ┌───────────────────────────────────┐
    │ release(token, remaining, reset)  │
    │ → Updates token budget            │
    │ → Notifies waiting workers        │
    └───────────────────────────────────┘

  Retry & Backoff Strategy

    Request fails with 5xx / timeout / 429
           │
           ▼
    attempt = 1, 2, 3, 4, 5 (max_retries=5)
           │
    delay = base_backoff × 2^(attempt-1) + random(0,1)
           │
    attempt 1: ~2s    (2×1 + jitter)
    attempt 2: ~4s    (2×2 + jitter)
    attempt 3: ~8s    (2×4 + jitter)
    attempt 4: ~16s   (2×8 + jitter)
    attempt 5: ~32s   (2×16 + jitter)
           │
    capped at 60s max
           │
    Still failing after 5 attempts?
    → Raise TransientError → checkpoint "pending"

  CLI Command Flow

    gh-discover ──► discover_top_users() ──► logins.txt
         │
         ▼
    gh-ingest ──► read logins.txt ──► Orchestrator.run()
         │                                │
         │                    ┌───────────┴───────────┐
         │                    │ Producer → Queue →     │
         │                    │ Workers → Storage      │
         │                    └───────────┬───────────┘
         │                                │
         ▼                                ▼
    gh-retry ──► SELECT FROM gh_checkpoints WHERE status='failed'
         │         AND attempt_count < max
         │
         ▼
         Re-queue failed logins ──► Orchestrator.run() again

  The same flow applies for hf-discover → hf-ingest → hf-retry.