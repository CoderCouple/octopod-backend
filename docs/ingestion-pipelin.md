╭─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Plan to implement                                                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ Plan: Pipeline Execution System with Control, UI Visibility, and Seed Strategy                                                                                                                      │
│                                                                                                                                                                                                     │
│ Context                                                                                                                                                                                             │
│                                                                                                                                                                                                     │
│ The product targets recruiters and hiring managers who search for developers by skills, experience, and languages. To be sellable to early customers, we need 50K+ searchable profiles with broad   │
│ coverage.                                                                                                                                                                                           │
│                                                                                                                                                                                                     │
│ Currently: the pipeline runs but has no visibility (UI can't show progress), no control (can't pause/stop), the embed step is a stub, and there's no strategy for bootstrapping data at scale. We   │
│ need to solve all of these so we can run a multi-hour ingestion pipeline, monitor it from the UI, control it, and end up with 50K+ searchable profiles in Qdrant.                                   │
│                                                                                                                                                                                                     │
│ Bootstrapping Strategy (Getting to 50K+)                                                                                                                                                            │
│                                                                                                                                                                                                     │
│ Three-phase ramp-up, each a pipeline run the UI can track:                                                                                                                                          │
│                                                                                                                                                                                                     │
│ ┌───────────────┬─────────────────────────────────────────────────────────┬──────────────────┬───────────────┬───────────────────────────────────┐                                                  │
│ │     Phase     │                        Pipeline                         │     Profiles     │ Time Estimate │              Purpose              │                                                  │
│ ├───────────────┼─────────────────────────────────────────────────────────┼──────────────────┼───────────────┼───────────────────────────────────┤                                                  │
│ │ 1. Quick Demo │ seed — GH discover top 1K → ingest → sync → embed       │ ~1K              │ ~30 min       │ Demoable to customers immediately │                                                  │
│ ├───────────────┼─────────────────────────────────────────────────────────┼──────────────────┼───────────────┼───────────────────────────────────┤                                                  │
│ │ 2. Scale Up   │ daily — GH top 25K + HF top 25K → ingest → sync → embed │ ~40-50K          │ ~4-8 hours    │ Core dataset for launch           │                                                  │
│ ├───────────────┼─────────────────────────────────────────────────────────┼──────────────────┼───────────────┼───────────────────────────────────┤                                                  │
│ │ 3. Enrich     │ weekly — LN discover + ingest → sync → embed            │ +10-20K enriched │ ~2-4 hours    │ LinkedIn data for recruiter value │                                                  │
│ └───────────────┴─────────────────────────────────────────────────────────┴──────────────────┴───────────────┴───────────────────────────────────┘                                                  │
│                                                                                                                                                                                                     │
│ The seed pipeline is a new fast-track pipeline: discover top N → ingest → sync → embed (no HF/LN). Gets profiles searchable in under an hour.                                                       │
│                                                                                                                                                                                                     │
│ Niche-targeted discovery — run multiple seed pipelines to fill talent categories:                                                                                                                   │
│                                                                                                                                                                                                     │
│ ┌──────────────┬─────────────────────────────────────────────────────────────┬───────────────────────────────────────────────────┬────────┐                                                         │
│ │    Niche     │                    GH Discovery Filters                     │               HF Discovery Filters                │ Target │                                                         │
│ ├──────────────┼─────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┼────────┤                                                         │
│ │ AI/ML        │ languages:[python] topics:[machine-learning, deep-learning] │ pipeline_tag:text-generation library:transformers │ 10K    │                                                         │
│ ├──────────────┼─────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┼────────┤                                                         │
│ │ Backend      │ languages:[go, java, rust] topics:[backend, microservices]  │ —                                                 │ 10K    │                                                         │
│ ├──────────────┼─────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┼────────┤                                                         │
│ │ Web3/Crypto  │ languages:[solidity, rust] topics:[blockchain, web3]        │ —                                                 │ 5K     │                                                         │
│ ├──────────────┼─────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┼────────┤                                                         │
│ │ Frontend     │ languages:[typescript, javascript] topics:[react, frontend] │ —                                                 │ 10K    │                                                         │
│ ├──────────────┼─────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┼────────┤                                                         │
│ │ DevOps/Infra │ languages:[go, python] topics:[kubernetes, devops]          │ —                                                 │ 5K     │                                                         │
│ ├──────────────┼─────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┼────────┤                                                         │
│ │ Data Eng     │ languages:[python, scala] topics:[data-engineering, spark]  │ pipeline_tag:tabular-classification               │ 5K     │                                                         │
│ ├──────────────┼─────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┼────────┤                                                         │
│ │ General      │ No filters, top by followers+stars                          │ No filters, top by downloads+likes                │ 10K    │                                                         │
│ └──────────────┴─────────────────────────────────────────────────────────────┴───────────────────────────────────────────────────┴────────┘                                                         │
│                                                                                                                                                                                                     │
│ Each niche is a separate seed pipeline run with languages and topics params. The UI shows each as a trackable workflow. Re-running is safe (checkpoint tables skip already-ingested users).         │
│                                                                                                                                                                                                     │
│ Data Flow Through Tables                                                                                                                                                                            │
│                                                                                                                                                                                                     │
│ STEP 1: DISCOVER                    STEP 2: INGEST                        STEP 3: BRIDGE SYNC (4-layer merge)                          STEP 4: EMBED                                                │
│ ─────────────────                   ──────────────                        ─────────────────────────────────────                         ─────────────                                               │
│                                                                                                                                                                                                     │
│ GitHub Search API ──► gh_users      gh_users ──► gh_repos                 ┌─────────────────────────────────────────────────────┐                                                                   │
│                       gh_checkpoints             gh_commits               │  Layer 1: Identity Resolution                       │                                                                   │
│                                                  gh_contributions         │  gh_users.login + hf_users.username                  │                                                                  │
│                                                  gh_checkpoints           │        ▼                                              │                                                                 │
│                                                                           │  developer_profile (dp_id created/found)             │                                                                  │
│ HF /api/models   ──► hf_users       hf_users ──► hf_models               │                                                      │                                                                   │
│                       hf_checkpoints              hf_datasets             │  Layer 2: Domain Merge                               │                                                                  │
│                                                   hf_spaces               │  gh_users + hf_users ──► developer_profile (merged)  │                                                                  │
│                                                   hf_checkpoints          │  ln_profiles ──────────► social_profile (merged)      │                                                                 │
│                                                                           │                                                      │                                                                  │
│ Proxycurl API    ──► ln_profiles     ln_profiles (enriched)               │  Layer 3: Aggregation                                │                                                                  │
│                       ln_checkpoints  ln_checkpoints                      │  developer_profile ─┐                                │                                                                  │
│                                                                           │                      ├──► aggregated_individual_     │       cohesive_individual_                                       │
│                                                                           │  social_profile ────┘     profile                    │       profile                                                    │
│                                                                           │                                                      │           │                                                      │
│                                                                           │  Layer 4: Cohesive Enrichment                        │           ├──► Qdrant (vectors)                                  │
│                                                                           │  aggregated_individual_profile                       │           │                                                      │
│                                                                           │        ▼                                              │           └──► OpenSearch (keywords)                            │
│                                                                           │  cohesive_individual_profile                         │                                                                  │
│                                                                           │  (+ embedding_text + scores)                         │                                                                  │
│                                                                           │                                                      │                                                                  │
│                                                                           │  merge_audit_log (decisions tracked per layer)       │                                                                  │
│                                                                           └─────────────────────────────────────────────────────┘                                                                   │
│                                                                                                                                                                                                     │
│ Table-level summary:                                                                                                                                                                                │
│                                                                                                                                                                                                     │
│ ┌────────────────────────────────────────┬──────────────────────────┬────────────────────────┬─────────────────────────────────────────────┐                                                        │
│ │                 Table                  │        Written By        │        Read By         │                   Purpose                   │                                                        │
│ ├────────────────────────────────────────┼──────────────────────────┼────────────────────────┼─────────────────────────────────────────────┤                                                        │
│ │ gh_users                               │ GH Discover + GH Ingest  │ Bridge Sync            │ Raw GitHub user profiles                    │                                                        │
│ ├────────────────────────────────────────┼──────────────────────────┼────────────────────────┼─────────────────────────────────────────────┤                                                        │
│ │ gh_repos, gh_commits, gh_contributions │ GH Ingest                │ Bridge Sync            │ Raw GitHub activity data                    │                                                        │
│ ├────────────────────────────────────────┼──────────────────────────┼────────────────────────┼─────────────────────────────────────────────┤                                                        │
│ │ gh_checkpoints                         │ GH Ingest                │ GH Ingest (skip check) │ Track ingestion progress per user           │                                                        │
│ ├────────────────────────────────────────┼──────────────────────────┼────────────────────────┼─────────────────────────────────────────────┤                                                        │
│ │ hf_users                               │ HF Discover + HF Ingest  │ Bridge Sync            │ Raw HuggingFace user profiles               │                                                        │
│ ├────────────────────────────────────────┼──────────────────────────┼────────────────────────┼─────────────────────────────────────────────┤                                                        │
│ │ hf_models, hf_datasets, hf_spaces      │ HF Ingest                │ Bridge Sync            │ Raw HuggingFace artifacts                   │                                                        │
│ ├────────────────────────────────────────┼──────────────────────────┼────────────────────────┼─────────────────────────────────────────────┤                                                        │
│ │ hf_checkpoints                         │ HF Ingest                │ HF Ingest (skip check) │ Track ingestion progress per user           │                                                        │
│ ├────────────────────────────────────────┼──────────────────────────┼────────────────────────┼─────────────────────────────────────────────┤                                                        │
│ │ ln_profiles                            │ LN Ingest                │ Bridge Sync            │ Raw LinkedIn profiles (via Proxycurl)       │                                                        │
│ ├────────────────────────────────────────┼──────────────────────────┼────────────────────────┼─────────────────────────────────────────────┤                                                        │
│ │ ln_checkpoints                         │ LN Ingest                │ LN Ingest (skip check) │ Track ingestion progress per URL            │                                                        │
│ ├────────────────────────────────────────┼──────────────────────────┼────────────────────────┼─────────────────────────────────────────────┤                                                        │
│ │ developer_profile                      │ Bridge Sync (Layer 1+2)  │ Bridge Sync (Layer 3)  │ Merged GH+HF identity + dev data            │                                                        │
│ ├────────────────────────────────────────┼──────────────────────────┼────────────────────────┼─────────────────────────────────────────────┤                                                        │
│ │ social_profile                         │ Bridge Sync (Layer 2)    │ Bridge Sync (Layer 3)  │ Merged LinkedIn + X social data             │                                                        │
│ ├────────────────────────────────────────┼──────────────────────────┼────────────────────────┼─────────────────────────────────────────────┤                                                        │
│ │ aggregated_individual_profile          │ Bridge Sync (Layer 3)    │ Bridge Sync (Layer 4)  │ Cross-domain aggregated profile             │                                                        │
│ ├────────────────────────────────────────┼──────────────────────────┼────────────────────────┼─────────────────────────────────────────────┤                                                        │
│ │ cohesive_individual_profile            │ Bridge Sync (Layer 4)    │ Embed, Search API      │ Final enriched profile + embedding_text     │                                                        │
│ ├────────────────────────────────────────┼──────────────────────────┼────────────────────────┼─────────────────────────────────────────────┤                                                        │
│ │ profile_ranking                        │ Bridge Sync / Ranking    │ Search API             │ Computed scores (activity, influence, etc.) │                                                        │
│ ├────────────────────────────────────────┼──────────────────────────┼────────────────────────┼─────────────────────────────────────────────┤                                                        │
│ │ merge_audit_log                        │ Bridge Sync (all layers) │ Debug/Admin            │ Field-level merge decisions + provenance    │                                                        │
│ ├────────────────────────────────────────┼──────────────────────────┼────────────────────────┼─────────────────────────────────────────────┤                                                        │
│ │ Qdrant (external)                      │ Embed step               │ Search API             │ Vector embeddings for semantic search       │                                                        │
│ ├────────────────────────────────────────┼──────────────────────────┼────────────────────────┼─────────────────────────────────────────────┤                                                        │
│ │ OpenSearch (external)                  │ Embed step               │ Search API             │ Keyword index for text search               │                                                        │
│ └────────────────────────────────────────┴──────────────────────────┴────────────────────────┴─────────────────────────────────────────────┘                                                        │
│                                                                                                                                                                                                     │
│ Pipeline execution tracking (new tables):                                                                                                                                                           │
│                                                                                                                                                                                                     │
│ ┌─────────────────────────┬────────────────────────────────────────────────────────────────┐                                                                                                        │
│ │          Table          │                            Purpose                             │                                                                                                        │
│ ├─────────────────────────┼────────────────────────────────────────────────────────────────┤                                                                                                        │
│ │ pipeline_execution      │ Top-level run (daily/weekly/seed) with status + control signal │                                                                                                        │
│ ├─────────────────────────┼────────────────────────────────────────────────────────────────┤                                                                                                        │
│ │ pipeline_execution_step │ Per-step progress within a pipeline (links to ingest_job)      │                                                                                                        │
│ ├─────────────────────────┼────────────────────────────────────────────────────────────────┤                                                                                                        │
│ │ ingest_job              │ Per-step job record (existing, linked via execution_phase_id)  │                                                                                                        │
│ ├─────────────────────────┼────────────────────────────────────────────────────────────────┤                                                                                                        │
│ │ ingest_job_item         │ Per-user item within a job (existing)                          │                                                                                                        │
│ └─────────────────────────┴────────────────────────────────────────────────────────────────┘                                                                                                        │
│                                                                                                                                                                                                     │
│ Changes                                                                                                                                                                                             │
│                                                                                                                                                                                                     │
│ 1. Add language/topic filters to GitHub Discovery                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ app/ingest/gh/discover.py — Add languages and topics params to discover_top_users():                                                                                                                │
│                                                                                                                                                                                                     │
│ Current signature:                                                                                                                                                                                  │
│ async def discover_top_users(config, n=5000, alpha=0.5, follower_bands=None, repo_pool_size=5000, enrich_concurrency=16)                                                                            │
│                                                                                                                                                                                                     │
│ New signature:                                                                                                                                                                                      │
│ async def discover_top_users(config, n=5000, alpha=0.5, follower_bands=None, repo_pool_size=5000, enrich_concurrency=16, languages=None, topics=None)                                               │
│                                                                                                                                                                                                     │
│ - languages: list[str] | None — GitHub languages to filter by (e.g., ["python", "rust"])                                                                                                            │
│ - topics: list[str] | None — GitHub topics to filter by (e.g., ["machine-learning", "web3"])                                                                                                        │
│                                                                                                                                                                                                     │
│ Implementation: Append language:{lang} and topic:{topic} to the GitHub Search API query strings in _collect_users_from_band() and _collect_top_repo_owners(). GitHub's search API supports these    │
│ natively.                                                                                                                                                                                           │
│                                                                                                                                                                                                     │
│ Output: list[UserCandidate] — each has login, followers, total_stars, score. No change to output shape.                                                                                             │
│                                                                                                                                                                                                     │
│ app/ingest/gh/config.py — No changes needed (filters are per-run params, not global config)                                                                                                         │
│                                                                                                                                                                                                     │
│ Discovery parameters summary:                                                                                                                                                                       │
│                                                                                                                                                                                                     │
│ ┌────────────────────┬─────────────┬───────────────┬────────────────────────────────────────────────────────┐                                                                                       │
│ │       Param        │    Type     │    Default    │                      Description                       │                                                                                       │
│ ├────────────────────┼─────────────┼───────────────┼────────────────────────────────────────────────────────┤                                                                                       │
│ │ n                  │ int         │ 5000          │ Return top N users                                     │                                                                                       │
│ ├────────────────────┼─────────────┼───────────────┼────────────────────────────────────────────────────────┤                                                                                       │
│ │ alpha              │ float       │ 0.5           │ Weight: 0=stars only, 1=followers only, 0.5=balanced   │                                                                                       │
│ ├────────────────────┼─────────────┼───────────────┼────────────────────────────────────────────────────────┤                                                                                       │
│ │ languages          │ list[str]   │ None          │ Filter by GitHub languages (python, rust, go, etc.)    │                                                                                       │
│ ├────────────────────┼─────────────┼───────────────┼────────────────────────────────────────────────────────┤                                                                                       │
│ │ topics             │ list[str]   │ None          │ Filter by GitHub topics (machine-learning, web3, etc.) │                                                                                       │
│ ├────────────────────┼─────────────┼───────────────┼────────────────────────────────────────────────────────┤                                                                                       │
│ │ min_repos          │ int         │ None          │ Minimum public repos (GH search: repos:>N)             │                                                                                       │
│ ├────────────────────┼─────────────┼───────────────┼────────────────────────────────────────────────────────┤                                                                                       │
│ │ min_followers      │ int         │ None          │ Override minimum follower threshold for band search    │                                                                                       │
│ ├────────────────────┼─────────────┼───────────────┼────────────────────────────────────────────────────────┤                                                                                       │
│ │ follower_bands     │ list[tuple] │ default bands │ Custom follower ranges for stratified search           │                                                                                       │
│ ├────────────────────┼─────────────┼───────────────┼────────────────────────────────────────────────────────┤                                                                                       │
│ │ repo_pool_size     │ int         │ 5000          │ How many top repos to scan for star counts             │                                                                                       │
│ ├────────────────────┼─────────────┼───────────────┼────────────────────────────────────────────────────────┤                                                                                       │
│ │ enrich_concurrency │ int         │ 16            │ Parallel user enrichment threads                       │                                                                                       │
│ └────────────────────┴─────────────┴───────────────┴────────────────────────────────────────────────────────┘                                                                                       │
│                                                                                                                                                                                                     │
│ Query building example for niche "AI/ML":                                                                                                                                                           │
│ followers:>500 language:python topic:machine-learning repos:>5                                                                                                                                      │
│                                                                                                                                                                                                     │
│ These params flow through: API request → pipeline input_params → runner step → discover_top_users()                                                                                                 │
│                                                                                                                                                                                                     │
│ 1b. Add filters to HuggingFace Discovery                                                                                                                                                            │
│                                                                                                                                                                                                     │
│ app/ingest/hf/discover.py — Add pipeline_tag and library params to discover_top_authors():                                                                                                          │
│                                                                                                                                                                                                     │
│ Current signature:                                                                                                                                                                                  │
│ async def discover_top_authors(config, n=5000, alpha=0.5, download_pool_size=20000, likes_pool_size=10000)                                                                                          │
│                                                                                                                                                                                                     │
│ New signature:                                                                                                                                                                                      │
│ async def discover_top_authors(config, n=5000, alpha=0.5, download_pool_size=20000, likes_pool_size=10000, pipeline_tag=None, library=None)                                                         │
│                                                                                                                                                                                                     │
│ - pipeline_tag: str | None — HF pipeline type filter (e.g., text-generation, image-classification, text-to-image)                                                                                   │
│ - library: str | None — Library filter (e.g., transformers, diffusers, pytorch)                                                                                                                     │
│                                                                                                                                                                                                     │
│ Implementation: Append ?pipeline_tag={tag}&library={lib} query params to the HF /api/models endpoint. The HuggingFace API natively supports these filters.                                          │
│                                                                                                                                                                                                     │
│ HF discovery parameters summary:                                                                                                                                                                    │
│                                                                                                                                                                                                     │
│ ┌────────────────────┬───────┬─────────┬──────────────────────────────────────────────────────────────┐                                                                                             │
│ │       Param        │ Type  │ Default │                         Description                          │                                                                                             │
│ ├────────────────────┼───────┼─────────┼──────────────────────────────────────────────────────────────┤                                                                                             │
│ │ n                  │ int   │ 5000    │ Return top N authors                                         │                                                                                             │
│ ├────────────────────┼───────┼─────────┼──────────────────────────────────────────────────────────────┤                                                                                             │
│ │ alpha              │ float │ 0.5     │ Weight: 0=likes only, 1=downloads only                       │                                                                                             │
│ ├────────────────────┼───────┼─────────┼──────────────────────────────────────────────────────────────┤                                                                                             │
│ │ pipeline_tag       │ str   │ None    │ HF task filter (text-generation, image-classification, etc.) │                                                                                             │
│ ├────────────────────┼───────┼─────────┼──────────────────────────────────────────────────────────────┤                                                                                             │
│ │ library            │ str   │ None    │ Library filter (transformers, diffusers, pytorch, etc.)      │                                                                                             │
│ ├────────────────────┼───────┼─────────┼──────────────────────────────────────────────────────────────┤                                                                                             │
│ │ download_pool_size │ int   │ 20000   │ Models to fetch by downloads                                 │                                                                                             │
│ ├────────────────────┼───────┼─────────┼──────────────────────────────────────────────────────────────┤                                                                                             │
│ │ likes_pool_size    │ int   │ 10000   │ Models to fetch by likes                                     │                                                                                             │
│ └────────────────────┴───────┴─────────┴──────────────────────────────────────────────────────────────┘                                                                                             │
│                                                                                                                                                                                                     │
│ 2. Database: pipeline_execution + pipeline_execution_step tables                                                                                                                                    │
│                                                                                                                                                                                                     │
│ sql/schema.sql — Add two new tables                                                                                                                                                                 │
│                                                                                                                                                                                                     │
│ pipeline_execution — groups steps into one trackable run:                                                                                                                                           │
│ - id TEXT PK (pe_ prefix)                                                                                                                                                                           │
│ - pipeline_type VARCHAR(30) — daily, weekly, seed                                                                                                                                                   │
│ - status VARCHAR(30) — pending, running, paused, completed, failed, cancelled                                                                                                                       │
│ - control_signal VARCHAR(30) — none, pause, cancel (runner polls between steps)                                                                                                                     │
│ - trigger, triggered_by, input_params JSONB                                                                                                                                                         │
│ - total_steps, completed_steps, current_step_order                                                                                                                                                  │
│ - started_at, completed_at, duration_ms, error_summary                                                                                                                                              │
│                                                                                                                                                                                                     │
│ pipeline_execution_step — one row per step within a pipeline:                                                                                                                                       │
│ - id TEXT PK (pes_ prefix)                                                                                                                                                                          │
│ - pipeline_execution_id FK → pipeline_execution                                                                                                                                                     │
│ - step_order INTEGER, step_name, step_label (for UI)                                                                                                                                                │
│ - status — pending, running, completed, failed, skipped, cancelled                                                                                                                                  │
│ - ingest_job_id TEXT — links to ingest_job.id once the step starts                                                                                                                                  │
│ - total_items, succeeded_count, failed_count, skipped_count                                                                                                                                         │
│ - started_at, completed_at, duration_ms, error_summary, stats JSONB                                                                                                                                 │
│                                                                                                                                                                                                     │
│ 3. Enums                                                                                                                                                                                            │
│                                                                                                                                                                                                     │
│ app/common/enum/ingest.py                                                                                                                                                                           │
│ - Add PipelineType enum: DAILY, WEEKLY, SEED                                                                                                                                                        │
│ - Add PipelineStatus enum: PENDING, RUNNING, PAUSED, COMPLETED, FAILED, CANCELLED                                                                                                                   │
│ - Add ControlSignal enum: NONE, PAUSE, CANCEL                                                                                                                                                       │
│ - Add PIPELINE_SEED and EMBED_SYNC to IngestJobType                                                                                                                                                 │
│                                                                                                                                                                                                     │
│ 4. Pipeline Execution Tracker                                                                                                                                                                       │
│                                                                                                                                                                                                     │
│ New file: app/ingest/pipeline/tracker.py                                                                                                                                                            │
│                                                                                                                                                                                                     │
│ PipelineTracker class (mirrors JobTracker pattern, raw asyncpg):                                                                                                                                    │
│ - create_execution(pipeline_type, steps, trigger, input_params) — inserts pipeline_execution + all pipeline_execution_step rows                                                                     │
│ - mark_execution_running(), mark_execution_completed(), mark_execution_failed(), mark_execution_paused(), mark_execution_cancelled()                                                                │
│ - mark_step_running(step_order, ingest_job_id), mark_step_completed(), mark_step_failed(), mark_step_skipped(), mark_step_cancelled()                                                               │
│ - update_step_progress(step_order, total, succeeded, failed, skipped) — live progress for UI polling                                                                                                │
│ - check_control_signal() → str — polls control_signal column between steps                                                                                                                          │
│ - clear_control_signal() — resets to none after processing                                                                                                                                          │
│ - Static: set_control_signal(pool, execution_id, signal) — called by API pause/cancel endpoints                                                                                                     │
│ - Static: get_execution(pool, execution_id) — returns execution + all steps (for GET endpoint)                                                                                                      │
│ - Static: get_active_executions(pool) — running or paused pipelines                                                                                                                                 │
│ - Static: resume_execution(pool, execution_id) — clears signal, sets status back to running                                                                                                         │
│                                                                                                                                                                                                     │
│ 5. Step Definitions                                                                                                                                                                                 │
│                                                                                                                                                                                                     │
│ New file: app/ingest/pipeline/steps.py                                                                                                                                                              │
│                                                                                                                                                                                                     │
│ Declarative step lists:                                                                                                                                                                             │
│ DAILY_STEPS = [                                                                                                                                                                                     │
│     {"name": "gh_discover",  "label": "GH Discover"},                                                                                                                                               │
│     {"name": "gh_ingest",    "label": "GH Ingest"},                                                                                                                                                 │
│     {"name": "hf_discover",  "label": "HF Discover"},                                                                                                                                               │
│     {"name": "hf_ingest",    "label": "HF Ingest"},                                                                                                                                                 │
│     {"name": "bridge_sync",  "label": "Bridge Sync"},                                                                                                                                               │
│     {"name": "embed",        "label": "Embed"},                                                                                                                                                     │
│ ]                                                                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ WEEKLY_STEPS = [                                                                                                                                                                                    │
│     {"name": "ln_discover",  "label": "LN Discover"},                                                                                                                                               │
│     {"name": "ln_ingest",    "label": "LN Ingest"},                                                                                                                                                 │
│     {"name": "bridge_sync",  "label": "Bridge Sync"},                                                                                                                                               │
│     {"name": "embed",        "label": "Embed"},                                                                                                                                                     │
│ ]                                                                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ SEED_STEPS = [                                                                                                                                                                                      │
│     {"name": "gh_discover",  "label": "GH Discover"},                                                                                                                                               │
│     {"name": "gh_ingest",    "label": "GH Ingest"},                                                                                                                                                 │
│     {"name": "bridge_sync",  "label": "Bridge Sync"},                                                                                                                                               │
│     {"name": "embed",        "label": "Embed"},                                                                                                                                                     │
│ ]                                                                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ 6. Refactored Pipeline Runner                                                                                                                                                                       │
│                                                                                                                                                                                                     │
│ app/ingest/pipeline/runner.py — Full rewrite                                                                                                                                                        │
│                                                                                                                                                                                                     │
│ Single unified run() method with control loop:                                                                                                                                                      │
│                                                                                                                                                                                                     │
│ async def run(self, pipeline_type, trigger, input_params, resume_from_step=None):                                                                                                                   │
│     steps = get_steps(pipeline_type)                                                                                                                                                                │
│     pt = PipelineTracker(pool)                                                                                                                                                                      │
│                                                                                                                                                                                                     │
│     # Create execution + all step rows upfront                                                                                                                                                      │
│     await pt.create_execution(pipeline_type, steps, ...)                                                                                                                                            │
│     await pt.mark_execution_running()                                                                                                                                                               │
│                                                                                                                                                                                                     │
│     for i, step_def in enumerate(steps, start=1):                                                                                                                                                   │
│         if i < resume_from_step: continue  # skip completed on resume                                                                                                                               │
│                                                                                                                                                                                                     │
│         # POLL control signal between steps                                                                                                                                                         │
│         signal = await pt.check_control_signal()                                                                                                                                                    │
│         if signal == "cancel":                                                                                                                                                                      │
│             mark remaining steps cancelled; return                                                                                                                                                  │
│         if signal == "pause":                                                                                                                                                                       │
│             mark execution paused; return                                                                                                                                                           │
│                                                                                                                                                                                                     │
│         # Execute step                                                                                                                                                                              │
│         await pt.mark_step_running(i)                                                                                                                                                               │
│         step_result = await self._execute_step(step_def["name"], input_params, pt, i)                                                                                                               │
│         await pt.mark_step_completed(i, step_result)                                                                                                                                                │
│                                                                                                                                                                                                     │
│     await pt.mark_execution_completed()                                                                                                                                                             │
│                                                                                                                                                                                                     │
│ Step dispatch: _execute_step() maps step name → existing logic (gh_discover, gh_ingest, etc.)                                                                                                       │
│                                                                                                                                                                                                     │
│ Each step internally creates its own ingest_job via JobTracker with execution_phase_id set to the pipeline execution ID.                                                                            │
│                                                                                                                                                                                                     │
│ Concurrency guard: Only one pipeline can be running at a time. Paused pipelines don't block.                                                                                                        │
│                                                                                                                                                                                                     │
│ 7. Implement Embed Step                                                                                                                                                                             │
│                                                                                                                                                                                                     │
│ New file: app/ingest/pipeline/embed.py                                                                                                                                                              │
│                                                                                                                                                                                                     │
│ batch_embed_from_db(pool, indexer, batch_size, pipeline_tracker, step_order):                                                                                                                       │
│ - Fetches all cohesive_individual_profile rows via asyncpg (explicit columns, no SELECT *)                                                                                                          │
│ - Skips profiles with no embedding_text or already-embedded (unless force=True)                                                                                                                     │
│ - Calls DualIndexer.batch_index() for each batch                                                                                                                                                    │
│ - Updates pipeline_tracker.update_step_progress() per batch for live UI updates                                                                                                                     │
│ - Returns stats dict {total, embedded, skipped, errors}                                                                                                                                             │
│                                                                                                                                                                                                     │
│ app/ingest/cli.py — Replace _embed() stub with real implementation using batch_embed_from_db                                                                                                        │
│                                                                                                                                                                                                     │
│ app/api/v1/controller/ingest_api.py — Replace _run_embed() stub similarly                                                                                                                           │
│                                                                                                                                                                                                     │
│ 8. Update JobTracker                                                                                                                                                                                │
│                                                                                                                                                                                                     │
│ app/ingest/common/job_tracker.py                                                                                                                                                                    │
│ - Add optional execution_phase_id parameter to create_job() — sets ingest_job.execution_phase_id to link the job to a pipeline execution                                                            │
│                                                                                                                                                                                                     │
│ 9. API Endpoints for Pipeline Control                                                                                                                                                               │
│                                                                                                                                                                                                     │
│ app/api/v1/controller/ingest_api.py — Add 7 new endpoints:                                                                                                                                          │
│                                                                                                                                                                                                     │
│ ┌──────────────────────────────┬────────┬────────────────────────────────────────────────────────────────────────────────────────┐                                                                  │
│ │           Endpoint           │ Method │                                        Purpose                                         │                                                                  │
│ ├──────────────────────────────┼────────┼────────────────────────────────────────────────────────────────────────────────────────┤                                                                  │
│ │ /ingest/pipeline/start       │ POST   │ Start a pipeline (daily/weekly/seed) with input_params (top, alpha, since_hours, etc.) │                                                                  │
│ ├──────────────────────────────┼────────┼────────────────────────────────────────────────────────────────────────────────────────┤                                                                  │
│ │ /ingest/pipeline/active      │ GET    │ Get currently running/paused pipeline(s)                                               │                                                                  │
│ ├──────────────────────────────┼────────┼────────────────────────────────────────────────────────────────────────────────────────┤                                                                  │
│ │ /ingest/pipeline/{id}        │ GET    │ Full execution details with all steps + live progress counts                           │                                                                  │
│ ├──────────────────────────────┼────────┼────────────────────────────────────────────────────────────────────────────────────────┤                                                                  │
│ │ /ingest/pipeline/{id}/pause  │ POST   │ Set control_signal=pause (current step finishes, then pauses)                          │                                                                  │
│ ├──────────────────────────────┼────────┼────────────────────────────────────────────────────────────────────────────────────────┤                                                                  │
│ │ /ingest/pipeline/{id}/resume │ POST   │ Clear signal, set status=running, dispatch background task from next pending step      │                                                                  │
│ ├──────────────────────────────┼────────┼────────────────────────────────────────────────────────────────────────────────────────┤                                                                  │
│ │ /ingest/pipeline/{id}/cancel │ POST   │ Set control_signal=cancel (current step finishes, remaining skip)                      │                                                                  │
│ ├──────────────────────────────┼────────┼────────────────────────────────────────────────────────────────────────────────────────┤                                                                  │
│ │ /ingest/pipeline/{id}/rerun  │ POST   │ Create new execution with same config, dispatch                                        │                                                                  │
│ └──────────────────────────────┴────────┴────────────────────────────────────────────────────────────────────────────────────────┘                                                                  │
│                                                                                                                                                                                                     │
│ GET /ingest/pipeline/{id} response shape (what the UI consumes):                                                                                                                                    │
│ {                                                                                                                                                                                                   │
│   "id": "pe_abc123",                                                                                                                                                                                │
│   "pipeline_type": "seed",                                                                                                                                                                          │
│   "status": "running",                                                                                                                                                                              │
│   "total_steps": 4,                                                                                                                                                                                 │
│   "completed_steps": 2,                                                                                                                                                                             │
│   "current_step_order": 3,                                                                                                                                                                          │
│   "started_at": "2026-04-23T10:00:00Z",                                                                                                                                                             │
│   "steps": [                                                                                                                                                                                        │
│     {"step_order": 1, "step_name": "gh_discover", "step_label": "GH Discover", "status": "completed", "total_items": 1000, "succeeded_count": 1000, "duration_ms": 45000},                          │
│     {"step_order": 2, "step_name": "gh_ingest", "step_label": "GH Ingest", "status": "completed", "total_items": 1000, "succeeded_count": 987, "failed_count": 13},                                 │
│     {"step_order": 3, "step_name": "bridge_sync", "step_label": "Bridge Sync", "status": "running", "total_items": 987, "succeeded_count": 234},                                                    │
│     {"step_order": 4, "step_name": "embed", "step_label": "Embed", "status": "pending"}                                                                                                             │
│   ]                                                                                                                                                                                                 │
│ }                                                                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ UI renders this as: [GH Discover ✓] → [GH Ingest ✓ 987/1000] → [Bridge Sync ⏳ 234/987] → [Embed ○]                                                                                                 │
│                                                                                                                                                                                                     │
│ 10. CLI Updates                                                                                                                                                                                     │
│                                                                                                                                                                                                     │
│ app/ingest/cli.py                                                                                                                                                                                   │
│ - Add pipeline-seed command with niche filters:                                                                                                                                                     │
│ python -m app.ingest.cli pipeline-seed --top 5000 --language python --topic machine-learning                                                                                                        │
│ python -m app.ingest.cli pipeline-seed --input logins.txt                                                                                                                                           │
│ python -m app.ingest.cli pipeline-seed --top 10000  # broad, no filters                                                                                                                             │
│ - Flags: --top, --alpha, --input, --login, --language (repeatable), --topic (repeatable), --min-repos, --hf-pipeline-tag, --hf-library                                                              │
│ - Update _pipeline_daily and _pipeline_weekly to use new PipelineRunner.run()                                                                                                                       │
│ - Update _embed() to use real implementation                                                                                                                                                        │
│                                                                                                                                                                                                     │
│ 11. Startup Recovery                                                                                                                                                                                │
│                                                                                                                                                                                                     │
│ app/main.py — Add startup hook:                                                                                                                                                                     │
│ - Query for pipeline_execution rows with status='running'                                                                                                                                           │
│ - Mark them as paused (not failed — data is fine, can be resumed)                                                                                                                                   │
│ - Logs a warning so the user knows to resume via API                                                                                                                                                │
│                                                                                                                                                                                                     │
│ Edge Cases                                                                                                                                                                                          │
│                                                                                                                                                                                                     │
│ - Server restart mid-pipeline: Execution auto-paused on startup, user resumes via API                                                                                                               │
│ - Pause while step running: Current step finishes first (step-level granularity), then pauses                                                                                                       │
│ - Two pipelines at once: Rejected with 409 — only one running pipeline allowed                                                                                                                      │
│ - Step failure: Execution marked failed. User can rerun (fresh start) — idempotent upserts make re-running safe                                                                                     │
│ - Resume after failure: Rerun creates new execution. Checkpoint tables skip already-ingested users.                                                                                                 │
│                                                                                                                                                                                                     │
│ Files                                                                                                                                                                                               │
│                                                                                                                                                                                                     │
│ New Files (4)                                                                                                                                                                                       │
│                                                                                                                                                                                                     │
│ ┌────────────────────────────────┬────────────────────────────────────────┐                                                                                                                         │
│ │              File              │                Purpose                 │                                                                                                                         │
│ ├────────────────────────────────┼────────────────────────────────────────┤                                                                                                                         │
│ │ app/ingest/pipeline/tracker.py │ PipelineTracker class                  │                                                                                                                         │
│ ├────────────────────────────────┼────────────────────────────────────────┤                                                                                                                         │
│ │ app/ingest/pipeline/steps.py   │ Step definitions (DAILY, WEEKLY, SEED) │                                                                                                                         │
│ ├────────────────────────────────┼────────────────────────────────────────┤                                                                                                                         │
│ │ app/ingest/pipeline/embed.py   │ batch_embed_from_db()                  │                                                                                                                         │
│ └────────────────────────────────┴────────────────────────────────────────┘                                                                                                                         │
│                                                                                                                                                                                                     │
│ Modified Files (9)                                                                                                                                                                                  │
│                                                                                                                                                                                                     │
│ ┌─────────────────────────────────────┬────────────────────────────────────────────────────────────┐                                                                                                │
│ │                File                 │                           Change                           │                                                                                                │
│ ├─────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                                                │
│ │ sql/schema.sql                      │ Add pipeline_execution + pipeline_execution_step tables    │                                                                                                │
│ ├─────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                                                │
│ │ app/common/enum/ingest.py           │ Add PipelineType, PipelineStatus, ControlSignal enums      │                                                                                                │
│ ├─────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                                                │
│ │ app/ingest/gh/discover.py           │ Add languages, topics, min_repos, min_followers params     │                                                                                                │
│ ├─────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                                                │
│ │ app/ingest/hf/discover.py           │ Add pipeline_tag, library params                           │                                                                                                │
│ ├─────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                                                │
│ │ app/ingest/common/job_tracker.py    │ Add execution_phase_id param to create_job()               │                                                                                                │
│ ├─────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                                                │
│ │ app/ingest/pipeline/runner.py       │ Full rewrite — unified run() with control loop             │                                                                                                │
│ ├─────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                                                │
│ │ app/api/v1/controller/ingest_api.py │ 7 new pipeline endpoints + real embed implementation       │                                                                                                │
│ ├─────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                                                │
│ │ app/ingest/cli.py                   │ Real _embed(), pipeline-seed command, updated daily/weekly │                                                                                                │
│ ├─────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                                                │
│ │ app/main.py                         │ Startup hook for stale pipeline recovery                   │                                                                                                │
│ └─────────────────────────────────────┴────────────────────────────────────────────────────────────┘                                                                                                │
│                                                                                                                                                                                                     │
│ Implementation Order                                                                                                                                                                                │
│                                                                                                                                                                                                     │
│ 1. Schema + enums (foundation)                                                                                                                                                                      │
│ 2. GH discovery filters (languages, topics, min_repos)                                                                                                                                              │
│ 3. HF discovery filters (pipeline_tag, library)                                                                                                                                                     │
│ 4. PipelineTracker (new file)                                                                                                                                                                       │
│ 5. Step definitions (new file)                                                                                                                                                                      │
│ 6. Embed implementation (new file)                                                                                                                                                                  │
│ 7. JobTracker update (execution_phase_id)                                                                                                                                                           │
│ 8. PipelineRunner rewrite                                                                                                                                                                           │
│ 9. API endpoints (7 new)                                                                                                                                                                            │
│ 10. CLI updates (seed + embed + daily/weekly with filter flags)                                                                                                                                     │
│ 11. Startup recovery hook                                                                                                                                                                           │
│ 12. Tests                                                                                                                                                                                           │
│                                                                                                                                                                                                     │
│ Verification                                                                                                                                                                                        │
│                                                                                                                                                                                                     │
│ 1. make test — all existing tests pass                                                                                                                                                              │
│ 2. make lint — no new errors                                                                                                                                                                        │
│ 3. Manual: python -m app.ingest.cli pipeline-seed --top 10 — runs 4 steps end-to-end                                                                                                                │
│ 4. Manual: python -m app.ingest.cli pipeline-seed --top 10 --language python --topic machine-learning — niche-filtered discovery                                                                    │
│ 5. Manual: POST /ingest/pipeline/start with {"pipeline_type": "seed", "input_params": {"top": 10}} — verify GET /ingest/pipeline/{id} shows step progress                                           │
│ 6. Manual: POST /ingest/pipeline/{id}/pause mid-run → verify pause → POST .../resume → verify continues                                                                                             │
│ 7. Manual: POST /ingest/pipeline/{id}/cancel → verify remaining steps marked cancelled                                                                                                              │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

╭─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Plan to implement                                                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ Plan: Independent/Dependent Pipeline Modes + Scheduling                                                                                                                                             │
│                                                                                                                                                                                                     │
│ Context                                                                                                                                                                                             │
│                                                                                                                                                                                                     │
│ The pipeline system was just implemented with daily/weekly/seed pipeline types, UI tracking, and pause/cancel support. Now we need:                                                                 │
│                                                                                                                                                                                                     │
│ 1. Independent mode — Run GH, HF, LN ingests individually as tracked pipeline executions, allowed to run in parallel with each other and with full pipelines                                        │
│ 2. Dependent mode — GH ingest → auto-discover HF/LN for those users → ingest them → sync → embed                                                                                                    │
│ 3. Scheduling — DB-based cron schedules + API (also supports external schedulers via existing POST endpoint)                                                                                        │
│                                                                                                                                                                                                     │
│ Changes                                                                                                                                                                                             │
│                                                                                                                                                                                                     │
│ 1. Enums — app/common/enum/ingest.py                                                                                                                                                                │
│                                                                                                                                                                                                     │
│ Add to PipelineType:                                                                                                                                                                                │
│ - GH_ONLY = "gh_only"                                                                                                                                                                               │
│ - HF_ONLY = "hf_only"                                                                                                                                                                               │
│ - LN_ONLY = "ln_only"                                                                                                                                                                               │
│ - DEPENDENT = "dependent"                                                                                                                                                                           │
│                                                                                                                                                                                                     │
│ Add to IngestTrigger:                                                                                                                                                                               │
│ - SCHEDULE = "schedule"                                                                                                                                                                             │
│                                                                                                                                                                                                     │
│ 2. Step Definitions — app/ingest/pipeline/steps.py                                                                                                                                                  │
│                                                                                                                                                                                                     │
│ Add 4 new step lists:                                                                                                                                                                               │
│                                                                                                                                                                                                     │
│ GH_ONLY_STEPS    = [gh_discover, gh_ingest]                                                                                                                                                         │
│ HF_ONLY_STEPS    = [hf_discover, hf_ingest]                                                                                                                                                         │
│ LN_ONLY_STEPS    = [ln_discover, ln_ingest]                                                                                                                                                         │
│ DEPENDENT_STEPS  = [gh_discover, gh_ingest, hf_crossref, hf_ingest, ln_crossref, ln_ingest, bridge_sync, embed]                                                                                     │
│                                                                                                                                                                                                     │
│ Update _STEP_MAP with all 4 new entries.                                                                                                                                                            │
│                                                                                                                                                                                                     │
│ 3. Crossref Steps — app/ingest/pipeline/runner.py                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ Two new step handlers + concurrency guard update:                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ _step_hf_crossref: Query hf_users WHERE github_username = ANY($1::text[]) using self._discovered_logins. Sets self._discovered_hf_usernames.                                                        │
│                                                                                                                                                                                                     │
│ _step_ln_crossref: Extract LinkedIn URLs from GH users via:                                                                                                                                         │
│ - gh_users.social_accounts JSONB (provider = 'LINKEDIN')                                                                                                                                            │
│ - gh_users.bio / website_url regex (linkedin.com/in/...)                                                                                                                                            │
│ - Insert found URLs into ln_pending_urls via LNStorage.upsert_pending_urls()                                                                                                                        │
│                                                                                                                                                                                                     │
│ Both added to the dispatch dict in _execute_step().                                                                                                                                                 │
│                                                                                                                                                                                                     │
│ Concurrency guard update: Full pipelines (daily, weekly, seed, dependent) block each other. Individual runs (gh_only, hf_only, ln_only) can run in parallel with anything. Same check in the API    │
│ pipeline_start endpoint.                                                                                                                                                                            │
│                                                                                                                                                                                                     │
│ 4. Schema — sql/schema.sql                                                                                                                                                                          │
│                                                                                                                                                                                                     │
│ Add pipeline_schedule table:                                                                                                                                                                        │
│                                                                                                                                                                                                     │
│ pipeline_schedule (                                                                                                                                                                                 │
│     id              TEXT PK,                                                                                                                                                                        │
│     name            VARCHAR(100) NOT NULL,                                                                                                                                                          │
│     pipeline_type   VARCHAR(30) NOT NULL,                                                                                                                                                           │
│     input_params    JSONB DEFAULT '{}',                                                                                                                                                             │
│     cron_expression VARCHAR(100) NOT NULL,                                                                                                                                                          │
│     is_enabled      BOOLEAN DEFAULT TRUE,                                                                                                                                                           │
│     last_run_at     TIMESTAMPTZ,                                                                                                                                                                    │
│     next_run_at     TIMESTAMPTZ,                                                                                                                                                                    │
│     created_at, updated_at                                                                                                                                                                          │
│ )                                                                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ 5. Scheduler Worker — NEW app/ingest/pipeline/scheduler.py                                                                                                                                          │
│                                                                                                                                                                                                     │
│ Simple async background loop (follows SendWorker pattern from app/outreach/send_worker.py):                                                                                                         │
│ - Polls every 60s: SELECT ... FROM pipeline_schedule WHERE is_enabled AND next_run_at <= now()                                                                                                      │
│ - For each due schedule: spawn PipelineRunner.run() as an asyncio.create_task                                                                                                                       │
│ - Update last_run_at and recompute next_run_at via croniter                                                                                                                                         │
│ - Module-level singleton pipeline_scheduler                                                                                                                                                         │
│                                                                                                                                                                                                     │
│ Dependency: croniter (lightweight cron parser, add to pyproject.toml)                                                                                                                               │
│                                                                                                                                                                                                     │
│ 6. API Endpoints — app/api/v1/controller/ingest_api.py                                                                                                                                              │
│                                                                                                                                                                                                     │
│ Update existing: pipeline_start concurrency guard (category-aware)                                                                                                                                  │
│                                                                                                                                                                                                     │
│ 4 new schedule CRUD endpoints:                                                                                                                                                                      │
│ - POST /ingest/schedule — create (validates cron via croniter.is_valid(), computes next_run_at)                                                                                                     │
│ - GET /ingest/schedules — list all                                                                                                                                                                  │
│ - PUT /ingest/schedule/{id} — update (enable/disable, change cron/params)                                                                                                                           │
│ - DELETE /ingest/schedule/{id} — delete                                                                                                                                                             │
│                                                                                                                                                                                                     │
│ 7. CLI — app/ingest/cli.py                                                                                                                                                                          │
│                                                                                                                                                                                                     │
│ 4 new commands:                                                                                                                                                                                     │
│ - pipeline-gh --top --alpha --language --topic                                                                                                                                                      │
│ - pipeline-hf --top --alpha --hf-pipeline-tag --hf-library                                                                                                                                          │
│ - pipeline-ln --max-profiles                                                                                                                                                                        │
│ - pipeline-dependent --top --alpha --since-hours --language --topic                                                                                                                                 │
│                                                                                                                                                                                                     │
│ 8. Startup Integration — app/main.py                                                                                                                                                                │
│                                                                                                                                                                                                     │
│ Add pipeline_scheduler.start() / .stop() to lifespan (same pattern as outreach workers).                                                                                                            │
│                                                                                                                                                                                                     │
│ Files                                                                                                                                                                                               │
│                                                                                                                                                                                                     │
│ ┌─────────────────────────────────────┬─────────────────────────────────────────────────────────────────┐                                                                                           │
│ │                File                 │                             Change                              │                                                                                           │
│ ├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤                                                                                           │
│ │ app/common/enum/ingest.py           │ Add 4 PipelineType values + SCHEDULE trigger                    │                                                                                           │
│ ├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤                                                                                           │
│ │ app/ingest/pipeline/steps.py        │ Add 4 step lists + update _STEP_MAP                             │                                                                                           │
│ ├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤                                                                                           │
│ │ app/ingest/pipeline/runner.py       │ Add crossref step handlers, update dispatch + concurrency guard │                                                                                           │
│ ├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤                                                                                           │
│ │ app/ingest/pipeline/scheduler.py    │ NEW — Background scheduler worker                               │                                                                                           │
│ ├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤                                                                                           │
│ │ app/api/v1/controller/ingest_api.py │ Update concurrency check + 4 schedule CRUD endpoints            │                                                                                           │
│ ├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤                                                                                           │
│ │ app/ingest/cli.py                   │ 4 new CLI commands                                              │                                                                                           │
│ ├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤                                                                                           │
│ │ app/main.py                         │ Start/stop scheduler in lifespan                                │                                                                                           │
│ ├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤                                                                                           │
│ │ sql/schema.sql                      │ Add pipeline_schedule table                                     │                                                                                           │
│ ├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤                                                                                           │
│ │ pyproject.toml                      │ Add croniter dependency                                         │                                                                                           │
│ └─────────────────────────────────────┴─────────────────────────────────────────────────────────────────┘                                                                                           │
│                                                                                                                                                                                                     │
│ Implementation Order                                                                                                                                                                                │
│                                                                                                                                                                                                     │
│ 1. Enums (PipelineType, IngestTrigger)                                                                                                                                                              │
│ 2. Step definitions (4 new step lists)                                                                                                                                                              │
│ 3. Crossref steps in runner + concurrency guard update                                                                                                                                              │
│ 4. CLI commands (pipeline-gh, pipeline-hf, pipeline-ln, pipeline-dependent)                                                                                                                         │
│ 5. Schema (pipeline_schedule table)                                                                                                                                                                 │
│ 6. Add croniter dependency                                                                                                                                                                          │
│ 7. Scheduler worker (new file)                                                                                                                                                                      │
│ 8. Schedule API endpoints (4 CRUD)                                                                                                                                                                  │
│ 9. Startup integration (main.py)                                                                                                                                                                    │
│ 10. Lint + test                                                                                                                                                                                     │
│                                                                                                                                                                                                     │
│ Verification                                                                                                                                                                                        │
│                                                                                                                                                                                                     │
│ 1. make test — all existing tests pass                                                                                                                                                              │
│ 2. make lint — no new errors                                                                                                                                                                        │
│ 3. CLI: python -m app.ingest.cli pipeline-gh --top 10 — runs gh_only pipeline                                                                                                                       │
│ 4. API: POST /ingest/pipeline/start {"pipeline_type": "gh_only"} — starts, shows in GET /pipeline/active                                                                                            │
│ 5. Parallel: Start gh_only and hf_only at the same time — both allowed                                                                                                                              │
│ 6. Blocked: Start daily while seed running — returns 409                                                                                                                                            │
│ 7. Dependent: POST /ingest/pipeline/start {"pipeline_type": "dependent", "input_params": {"top": 10}} — runs all 8 steps including crossref                                                         │
│ 8. Schedule: POST /ingest/schedule {"name": "nightly", "pipeline_type": "daily", "cron_expression": "0 2 * * *"} — creates schedule, scheduler picks it up                                          │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯


