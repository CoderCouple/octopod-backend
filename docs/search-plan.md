──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
 Ready to code?                                                                                                                                                                                   
                                                                                                                                                                                                  
 Here is Claude's plan:                                 
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
 Plan: Semantic Search Pipeline — Reranker + Hybrid Search + Scale

 Context

 We need production-grade semantic search over 5M+ GitHub developer profiles (growing exponentially). The current ProfileSearchService does basic Qdrant vector search with 4 filters. Missing:
 reranker, hybrid keyword search, richer embedding text, batch embedding, Qdrant scale tuning, and has an N+1 DB query bug.

 Target pipeline:
 Query → embed → ANN vector search + keyword search (parallel)
      → RRF fusion → top 200 → cross-encoder rerank → final top 20

 Decisions: Local cross-encoder (bge-reranker-v2-m3), Postgres tsvector for BM25, keep all-MiniLM-L6-v2 (384d).

 ---
 Phase 1: Reranker Module

 New files:

 app/service/reranking/__init__.py

 - RerankCandidate dataclass: profile_id, text, original_score
 - RerankResult dataclass: profile_id, rerank_score, original_score
 - Reranker(ABC) with async rerank(query, candidates, top_k) → list[RerankResult]

 app/service/reranking/cross_encoder_reranker.py

 - CrossEncoderReranker(Reranker) — lazy-loads bge-reranker-v2-m3 via sentence_transformers.CrossEncoder
 - Global _model singleton, same pattern as sentence_transformer_provider.py
 - predict() on [[query, text], ...] pairs → sort by score desc

 app/settings.py — add fields

 - reranker_model: str = "BAAI/bge-reranker-v2-m3"
 - reranker_enabled: bool = True

 pyproject.toml — add dependency

 - sentence-transformers already present (used by embedding provider)

 tests/test_services/test_reranking.py

 - MockReranker using word-overlap scoring
 - Tests: sorted output, top_k limit, empty input, profile_id preservation

 ---
 Phase 2: Hybrid Search — Postgres tsvector

 sql/search_tsv_migration.sql (new)

 ALTER TABLE cohesive_profile ADD COLUMN IF NOT EXISTS search_tsv tsvector;
 CREATE INDEX IF NOT EXISTS idx_cohesive_profile_search_tsv
     ON cohesive_profile USING GIN (search_tsv);
 -- Trigger: auto-populate search_tsv from embedding_text on INSERT/UPDATE
 -- Backfill: UPDATE cohesive_profile SET search_tsv = to_tsvector('english', COALESCE(embedding_text, ''));

 app/model/cohesive_profile_model.py — add column

 - search_tsv = Column(TSVECTOR, nullable=True) (from sqlalchemy.dialects.postgresql)

 app/db/repository/cohesive_profile_repository.py — add method

 - keyword_search(query, limit, filters) → list[tuple[CohesiveProfile, float]]
 - Uses plainto_tsquery('english', query) + ts_rank()
 - Applies same metadata filters (languages via JSONB ?|, min_stars, etc.)

 Alembic migration

 - poetry run alembic revision --autogenerate -m "add_search_tsv"
 - Manually add GIN index + trigger in upgrade()

 ---
 Phase 3: RRF Fusion + Rewrite Search Pipeline

 app/service/search/__init__.py (new, empty)

 app/service/search/fusion.py (new)

 - FusedResult dataclass: profile_id, rrf_score, vector_score, keyword_score, vector_rank, keyword_rank
 - reciprocal_rank_fusion(vector_results, keyword_results, k=60) → list[FusedResult]
 - Handles deduplication (same profile in both lists → summed RRF scores)

 app/service/profile_search_service.py — rewrite search()

 New pipeline:
 1. Embed query → query_vector
 2. Parallel search — asyncio.gather(vector_search, keyword_search)
   - Vector: Qdrant search with limit = min(request.limit * 15, 300) (over-fetch)
   - Keyword: Postgres tsvector ts_rank (graceful fallback if fails, e.g. SQLite in tests)
 3. RRF fusion — merge + deduplicate + sort by fused score
 4. Rerank (if request.rerank=True and reranker enabled) — top 200 candidates → cross-encoder → sorted
 5. Batch fetch — cp_repo.list_by_ids(final_ids) + pr_repo.list_by_cohesive_profile_ids(final_ids) — fixes N+1
 6. Return top-K SearchResultResponse in score order

 New private methods:
 - _vector_search(query_vector, request, limit) → hits
 - _keyword_search(query, request, limit) → list[tuple[str, float]]
 - _build_qdrant_filter(filters) → Filter | None (extracted from current inline code)
 - _build_payload(cp) → dict (shared between upsert and batch)

 Constructor: add reranker: Reranker | None = None param, _get_reranker() lazy loader.

 app/api/v1/request/developer_profile_request.py

 - Add rerank: bool = Field(default=True) to SemanticSearchRequest

 tests/test_services/test_fusion.py (new)

 - test_rrf_basic_fusion — profiles in both lists get highest scores
 - test_rrf_empty_lists, test_rrf_one_empty_list
 - test_rrf_deduplication — same profile in both lists → single entry with summed score

 tests/test_services/test_profile_search.py — update

 - Pass MockReranker to ProfileSearchService constructor
 - Add: test_search_with_reranking, test_search_without_reranking

 ---
 Phase 4: Richer Embedding Text + More Filters

 app/service/profile_merge_service.py — update _build_embedding_text()

 Add (ordered by importance for 256-token truncation):
 - Location: "Located in {location}"
 - Contributions: "{total_contributions} contributions"
 - Top 5 repo descriptions: "Repo {name}: {description}"
 - Social accounts from platform_data
 - Website URL

 Change signature: _build_embedding_text(cp, platform_data=None) — backward-compatible.
 Update 2 call sites in merge_profile() to pass platform_data.

 app/service/profile_search_service.py — extend _build_payload()

 Add to Qdrant payload:
 - location (lowercased), company (lowercased)
 - topics, total_contributions, total_followers, total_hf_downloads

 _build_qdrant_filter() — add filter support

 New filters: location (MatchValue), company (MatchValue), topics (MatchAny), min_contributions (Range), min_followers (Range)

 ---
 Phase 5: Batch Embedding + Qdrant Optimization

 app/service/profile_search_service.py — add batch_embed_profiles()

 - batch_embed_profiles(batch_size=100, force=False, progress_callback=None) → dict
 - Iterates all CohesiveProfiles, embeds, upserts to Qdrant in batches
 - Skips already-embedded unless force=True
 - Returns {total, embedded, skipped, errors}

 app/db/qdrant_client.py — update ensure_collection()

 - HNSW tuning: m=16, ef_construct=200
 - Scalar quantization: INT8, quantile=0.99, always_ram=True — 4x memory reduction
 - Create payload indexes for all filterable fields (keyword for arrays/strings, integer for numerics)

 API endpoint for batch embedding

 - POST /developer-profile/embed-all in developer_profile_api.py
 - Params: batch_size, force
 - Runs as background task, returns job-like status

 Makefile

 - make embed-profiles target

 ---
 Files to Modify/Create

 ┌──────────────────────────────────────────────────┬────────────────────────────────────────────────┐
 │                       File                       │                     Action                     │
 ├──────────────────────────────────────────────────┼────────────────────────────────────────────────┤
 │ app/service/reranking/__init__.py                │ Create — Reranker ABC + dataclasses            │
 ├──────────────────────────────────────────────────┼────────────────────────────────────────────────┤
 │ app/service/reranking/cross_encoder_reranker.py  │ Create — CrossEncoder impl                     │
 ├──────────────────────────────────────────────────┼────────────────────────────────────────────────┤
 │ app/service/search/__init__.py                   │ Create — empty                                 │
 ├──────────────────────────────────────────────────┼────────────────────────────────────────────────┤
 │ app/service/search/fusion.py                     │ Create — RRF fusion                            │
 ├──────────────────────────────────────────────────┼────────────────────────────────────────────────┤
 │ sql/search_tsv_migration.sql                     │ Create — tsvector column + GIN index + trigger │
 ├──────────────────────────────────────────────────┼────────────────────────────────────────────────┤
 │ app/settings.py                                  │ Modify — add reranker_model, reranker_enabled  │
 ├──────────────────────────────────────────────────┼────────────────────────────────────────────────┤
 │ app/model/cohesive_profile_model.py              │ Modify — add search_tsv column                 │
 ├──────────────────────────────────────────────────┼────────────────────────────────────────────────┤
 │ app/db/repository/cohesive_profile_repository.py │ Modify — add keyword_search()                  │
 ├──────────────────────────────────────────────────┼────────────────────────────────────────────────┤
 │ app/service/profile_search_service.py            │ Rewrite — full pipeline                        │
 ├──────────────────────────────────────────────────┼────────────────────────────────────────────────┤
 │ app/service/profile_merge_service.py             │ Modify — richer _build_embedding_text()        │
 ├──────────────────────────────────────────────────┼────────────────────────────────────────────────┤
 │ app/api/v1/request/developer_profile_request.py  │ Modify — add rerank field                      │
 ├──────────────────────────────────────────────────┼────────────────────────────────────────────────┤
 │ app/api/v1/controller/developer_profile_api.py   │ Modify — add embed-all endpoint                │
 ├──────────────────────────────────────────────────┼────────────────────────────────────────────────┤
 │ app/db/qdrant_client.py                          │ Modify — HNSW + quantization + payload indexes │
 ├──────────────────────────────────────────────────┼────────────────────────────────────────────────┤
 │ tests/test_services/test_reranking.py            │ Create                                         │
 ├──────────────────────────────────────────────────┼────────────────────────────────────────────────┤
 │ tests/test_services/test_fusion.py               │ Create                                         │
 ├──────────────────────────────────────────────────┼────────────────────────────────────────────────┤
 │ tests/test_services/test_profile_search.py       │ Modify — update for new pipeline               │
 └──────────────────────────────────────────────────┴────────────────────────────────────────────────┘

 Verification

 1. make test — all existing + new tests pass
 2. psql -f sql/search_tsv_migration.sql — tsvector column + index created
 3. POST /developer-profile/embed-all {"force": true} — bulk embeds all profiles
 4. POST /developer-profile/search {"query": "machine learning engineer in San Francisco", "filters": {"languages": ["Python"], "min_stars": 50}, "rerank": true} — returns reranked results
 5. Verify N+1 fix: search with limit=20 makes 2 DB queries (not 20+)
 6. docker exec qdrant curl localhost:6333/collections/developer_profiles — confirm quantization + HNSW config
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌

                                                                                                                                                                                             
  Results                                                                                                                                                                                         
                                                                                                                                                                                                  
  ┌─────────────────────────────────────────────────────────────────────┬───────────────────────────────────┐                                                                                     
  │                                Test                                 │              Result               │
  ├─────────────────────────────────────────────────────────────────────┼───────────────────────────────────┤                                                                                     
  │ Unit tests (make test)                                              │ 143/143 passed                    │                                                                                     
  ├─────────────────────────────────────────────────────────────────────┼───────────────────────────────────┤                                                                                     
  │ Test 1: ML search → Yann LeCun first                                │ Correct                           │                                                                                     
  ├─────────────────────────────────────────────────────────────────────┼───────────────────────────────────┤                                                                                     
  │ Test 2: Linux kernel → Torvalds first                               │ Correct                           │                                                                                     
  ├─────────────────────────────────────────────────────────────────────┼───────────────────────────────────┤
  │ Test 3: Python creator → Guido first                                │ Correct                           │
  ├─────────────────────────────────────────────────────────────────────┼───────────────────────────────────┤
  │ Test 4: Filter languages=["Python"] → excludes Torvalds             │ Correct                           │
  ├─────────────────────────────────────────────────────────────────────┼───────────────────────────────────┤
  │ Test 5: Filter min_stars=100000 → only Torvalds                     │ Correct                           │
  ├─────────────────────────────────────────────────────────────────────┼───────────────────────────────────┤
  │ Test 6: Reranking "SF + ML" → Guido 0.16, LeCun 0.002               │ Correct                           │
  ├─────────────────────────────────────────────────────────────────────┼───────────────────────────────────┤
  │ Test 7: Impossible filter → empty results                           │ Correct                           │
  ├─────────────────────────────────────────────────────────────────────┼───────────────────────────────────┤
  │ Test 8: Keyword-heavy "convolutional neural networks" → LeCun first │ Correct (hybrid tsvector working) │
  ├─────────────────────────────────────────────────────────────────────┼───────────────────────────────────┤
  │ Test 9: POST /embed-all → 202 started                               │ Correct                           │
  ├─────────────────────────────────────────────────────────────────────┼───────────────────────────────────┤
  │ Test 10: Qdrant HNSW m=16, ef_construct=200, INT8 quantization      │ Confirmed                         │
  ├─────────────────────────────────────────────────────────────────────┼───────────────────────────────────┤
  │ Test 11: "Portland Oregon" → Torvalds first (boosted by RRF fusion) │ Correct                           │
  ├─────────────────────────────────────────────────────────────────────┼───────────────────────────────────┤
  │ Test 12: Full pipeline (rerank + filters + hybrid)                  │ Correct                           │
  └─────────────────────────────────────────────────────────────────────┴───────────────────────────────────┘

  Also fixed during testing:
  - Updated client.search() → client.query_points() for qdrant-client v1.11+
  - Added ensure_collection() call to app lifespan startup
                                                                                                                                                                                                  
⏺ Search Architecture — Detailed Explanation                                                                                                                                                      
                                                            
  High-Level Pipeline                                                                                                                                                                             
                                                                                                                                                                                                  
                              User Query                                                                                                                                                          
                                  |                                                                                                                                                               
                      "machine learning engineer            
                       in San Francisco"
                                  |
                                  v
                    ┌─────────────────────────┐
                    │   STEP 1: EMBED QUERY   │
                    │   all-MiniLM-L6-v2      │
                    │   text -> 384-dim vector │
                    └────────────┬────────────┘
                                 |
                ┌────────────────┼────────────────┐
                |                                  |
                v                                  v
  ┌──────────────────────┐          ┌──────────────────────────┐
  │  STEP 2a: VECTOR     │          │  STEP 2b: KEYWORD        │
  │  SEARCH (Qdrant)     │          │  SEARCH (Postgres)       │
  │                      │          │                          │
  │  ANN cosine search   │          │  tsvector + ts_rank()    │
  │  384-dim HNSW index  │          │  GIN index on search_tsv │
  │  limit = 300         │          │  limit = 200             │
  │  + payload filters   │          │  + SQL column filters    │
  │                      │          │                          │
  │  Returns:            │          │  Returns:                │
  │  (profile_id, score) │          │  (profile_id, ts_rank)   │
  │  sorted by cosine    │          │  sorted by relevance     │
  │  similarity          │          │  to query terms          │
  └──────────┬───────────┘          └──────────┬───────────────┘
             |        asyncio.gather()         |
             |     (runs both in parallel)     |
             └────────────────┬────────────────┘
                              |
                              v
                ┌─────────────────────────────┐
                │  STEP 3: RRF FUSION         │
                │                             │
                │  Reciprocal Rank Fusion     │
                │  k = 60                     │
                │                             │
                │  score = Σ 1/(k + rank_i)   │
                │                             │
                │  Profiles in BOTH lists     │
                │  get summed scores (boost)  │
                │                             │
                │  Deduplicates + merges      │
                │  Returns: sorted FusedResult│
                └──────────────┬──────────────┘
                               |
                  ┌────────────┴────────────┐
                  |                         |
            rerank=true              rerank=false
                  |                         |
                  v                         v
  ┌───────────────────────────┐   ┌─────────────────┐
  │  STEP 4: CROSS-ENCODER    │   │  Take top-K     │
  │  RERANKING                │   │  by RRF score   │
  │                           │   └────────┬────────┘
  │  Model: bge-reranker-v2-m3│           |
  │  Top 200 candidates       │           |
  │                           │           |
  │  For each candidate:      │           |
  │    score = model.predict( │           |
  │      [query, profile_text]│           |
  │    )                      │           |
  │                           │           |
  │  Sort by rerank_score     │           |
  │  Return top-K             │           |
  └─────────────┬─────────────┘           |
                |                         |
                └────────────┬────────────┘
                             |
                             v
                ┌─────────────────────────────┐
                │  STEP 5: BATCH FETCH        │
                │                             │
                │  2 queries total (not N+1): │
                │  • cp_repo.list_by_ids()    │
                │  • pr_repo.list_by_ids()    │
                │                             │
                │  Build response in score    │
                │  order from final_ids       │
                └──────────────┬──────────────┘
                               |
                               v
                      SearchResultResponse[]
                      [{profile, score, ranking}]

  ---
  Step-by-Step Walkthrough

  Step 1: Query Embedding

  Input:  "machine learning engineer in San Francisco"
  Model:  all-MiniLM-L6-v2 (SentenceTransformers)
  Output: [0.023, -0.081, 0.142, ...] (384 floats, L2-normalized)

  The SentenceTransformerProvider uses a global singleton model (lazy-loaded on first call). The query text is encoded into a 384-dimensional dense vector that captures semantic meaning.
  "machine learning engineer" and "ML researcher" will produce similar vectors even though they share few exact words.

  File: app/service/embedding/sentence_transformer_provider.py

  ---
  Step 2a: Vector Search (Qdrant) — Semantic Similarity

  Query vector ──> Qdrant HNSW index ──> top 300 nearest neighbors
                      |
                      ├── payload filters applied BEFORE ANN scan
                      |   languages ∈ ["Python"]         (MatchAny)
                      |   total_stars >= 50               (Range)
                      |   location == "san francisco"     (MatchValue)
                      |   topics ∈ ["ml", "ai"]           (MatchAny)
                      |
                      └── Returns: [(cp_id, cosine_score), ...]

  How it works:
  - Qdrant stores each profile as a point = {vector: [384 floats], payload: {metadata}}
  - HNSW (Hierarchical Navigable Small World) graph enables O(log n) approximate nearest neighbor search
  - Payload indexes (GIN for keywords, B-tree for integers) enable pre-filtering before the ANN scan
  - Over-fetches by 15x (limit * 15, capped at 300) to give the fusion step a large candidate pool

  Qdrant collection config:
  HNSW:          m=16, ef_construct=200  (higher recall, more build time)
  Quantization:  INT8, quantile=0.99    (4x memory reduction, ~1% accuracy loss)
  Payload indexes on: languages, skills, topics, location, company,
                      total_stars, years_of_experience, total_contributions,
                      total_followers, total_hf_downloads

  File: app/service/profile_search_service.py:_vector_search()

  ---
  Step 2b: Keyword Search (Postgres tsvector) — Lexical Matching

  Query text ──> plainto_tsquery('english', query)
                      |
                      ├── Matches against search_tsv column (GIN index)
                      |   search_tsv is auto-populated by trigger from embedding_text
                      |
                      ├── ts_rank() scores each match by term frequency
                      |
                      ├── Same metadata filters applied via SQL WHERE:
                      |   languages ?| ARRAY['Python']    (JSONB overlap)
                      |   total_stars >= 50               (integer compare)
                      |   lower(location) = 'san francisco'
                      |
                      └── Returns: [(cp_id, ts_rank_score), ...]

  Why both vector AND keyword search?
  Vector search is great at:              Keyword search is great at:
    "ML engineer" ≈ "data scientist"        Exact name matches: "Torvalds"
    Semantic similarity                     Specific terms: "PostgreSQL 16"
    Conceptual matching                     Location names: "Portland Oregon"
                                            Acronyms: "CNN", "LSTM"

  Vector search misses exact matches; keyword search misses semantics. Together they cover both.

  Graceful fallback: If Postgres isn't available (e.g., SQLite in tests), keyword search returns [] and the pipeline degrades to vector-only — no crash.

  File: app/db/repository/cohesive_profile_repository.py:keyword_search()

  ---
  Step 3: Reciprocal Rank Fusion (RRF)

  Vector results (ranked by cosine):     Keyword results (ranked by ts_rank):
    Rank 1: Yann LeCun    (0.89)          Rank 1: Yann LeCun    (0.42)
    Rank 2: Guido         (0.71)          Rank 2: Linus         (0.31)
    Rank 3: Linus         (0.65)          Rank 3: Guido         (0.18)

  RRF formula:  score(d) = Σ  1 / (k + rank_i)    where k = 60

  LeCun:   1/(60+1) + 1/(60+1)  = 0.01639 + 0.01639 = 0.03279  ← highest (in both!)
  Guido:   1/(60+2) + 1/(60+3)  = 0.01613 + 0.01587 = 0.03200
  Linus:   1/(60+3) + 1/(60+2)  = 0.01587 + 0.01613 = 0.03200

  Key insight: Profiles appearing in both result lists get their RRF scores summed, naturally boosting profiles that are relevant by both semantic and lexical criteria. The constant k=60 dampens
   the effect of rank position — rank 1 vs rank 5 matters less than "appeared in both lists vs one list."

  Deduplication is built in: same profile_id in both lists produces a single FusedResult with summed score.

  File: app/service/search/fusion.py:reciprocal_rank_fusion()

  ---
  Step 4: Cross-Encoder Reranking (Optional)

  Top 200 fused candidates
           |
           v
  ┌─────────────────────────────────────────────┐
  │  Cross-Encoder: bge-reranker-v2-m3          │
  │                                             │
  │  Input pairs:                               │
  │    ["ML engineer in SF", "Deep learning..."]│
  │    ["ML engineer in SF", "Python creator..."]│
  │    ["ML engineer in SF", "Linux kernel..."] │
  │                                             │
  │  Unlike embedding (encode separately),      │
  │  cross-encoder sees query + document        │
  │  TOGETHER → much more accurate but slower   │
  │                                             │
  │  Output: relevance score per pair           │
  │    LeCun:  0.847  ← query-document attention│
  │    Guido:  0.159                            │
  │    Linus:  0.003                            │
  └─────────────────────────────────────────────┘

  Why rerank?
  - Bi-encoder (Step 1): Encodes query and document separately. Fast (O(1) per query against pre-computed index) but less precise — can't model fine-grained query-document interactions.
  - Cross-encoder (Step 4): Encodes query and document together through full transformer attention. Much more accurate but O(n) — can't search millions, only score ~200 candidates.

  This is the standard retrieve-then-rerank pattern:
  1. Cheap retrieval: 5M profiles → 200 candidates (vector + keyword)
  2. Expensive reranking: 200 candidates → 20 final results (cross-encoder)

  Controlled by: request.rerank=true (default) and settings.reranker_enabled

  File: app/service/reranking/cross_encoder_reranker.py

  ---
  Step 5: Batch Fetch (N+1 Fix)

  BEFORE (old code — N+1 problem):
    for hit in hits:                    # 20 hits
      cp = await cp_repo.get_by_id()    # 20 SQL queries
      rank = await pr_repo.get_by_id()  # 20 SQL queries
                                        # Total: 40 queries

  AFTER (new code — batch):
    profiles = await cp_repo.list_by_ids(final_ids)    # 1 SQL query (WHERE id IN (...))
    rankings = await pr_repo.list_by_cohesive_ids(...)  # 1 SQL query (WHERE id IN (...))
                                                        # Total: 2 queries

  Results are assembled in score order (preserved from final_ids list) using dict lookups, then serialized to SearchResultResponse.

  ---
  Data Flow: How Profiles Get Indexed

  ┌──────────────────────────────────────────────────────────────┐
  │                    INDEXING PIPELINE                          │
  │                                                              │
  │  GitHub/HF/LinkedIn data                                     │
  │       |                                                      │
  │       v                                                      │
  │  ProfileMergeService._merge_fields()                         │
  │       |  Merges fields from all platforms with priority       │
  │       v                                                      │
  │  ProfileMergeService._build_embedding_text()                 │
  │       |  Generates rich text from profile:                    │
  │       |    "Deep learning and AI researcher.                  │
  │       |     Chief AI Scientist at Meta.                       │
  │       |     Located in New York, New York.                    │
  │       |     Skills: deep-learning, machine-learning...        │
  │       |     Languages: Python, C++, Lua.                      │
  │       |     5000 contributions. 30000 GitHub stars.           │
  │       |     Repo pytorch: Deep learning framework..."         │
  │       v                                                      │
  │  Stored in cohesive_profile.embedding_text                   │
  │       |                                                      │
  │       ├──> Postgres trigger auto-populates search_tsv        │
  │       |    to_tsvector('english', embedding_text)             │
  │       |    (used by keyword search)                           │
  │       |                                                      │
  │       └──> ProfileSearchService.upsert_profile()             │
  │            or batch_embed_profiles()                          │
  │               |                                              │
  │               ├── embed(text) → 384-dim vector               │
  │               ├── _build_payload() → filterable metadata     │
  │               └── qdrant.upsert(point_id, vector, payload)   │
  │                   (used by vector search)                     │
  └──────────────────────────────────────────────────────────────┘

  ---
  Component Dependency Map

  ProfileSearchService
  ├── EmbeddingProvider (ABC)
  │   └── SentenceTransformerProvider  ← all-MiniLM-L6-v2 (lazy singleton)
  │
  ├── QdrantClient
  │   └── Collection: developer_profiles
  │       ├── HNSW index (m=16, ef=200)
  │       ├── INT8 scalar quantization
  │       └── Payload indexes (keyword + integer)
  │
  ├── Reranker (ABC)
  │   └── CrossEncoderReranker  ← bge-reranker-v2-m3 (lazy singleton)
  │
  ├── CohesiveProfileRepository
  │   ├── list_by_ids()       ← batch fetch (Step 5)
  │   └── keyword_search()    ← tsvector search (Step 2b)
  │
  ├── ProfileRankingRepository
  │   └── list_by_cohesive_profile_ids()  ← batch fetch (Step 5)
  │
  └── fusion.reciprocal_rank_fusion()     ← RRF merge (Step 3)

  ---
  Filter Architecture

  Filters are applied twice — once in each search path — ensuring consistent results:

  Request filters: {"languages": ["Python"], "min_stars": 50, "location": "San Francisco"}
                      |                                        |
       ┌──────────────┴──────────────┐          ┌─────────────┴─────────────┐
       │  Qdrant payload filters     │          │  Postgres SQL WHERE       │
       │                             │          │                           │
       │  FieldCondition(            │          │  languages ?| ARRAY[...]  │
       │    key="languages",         │          │  total_stars >= 50        │
       │    match=MatchAny(["Py"])   │          │  lower(location) = '...' │
       │  )                          │          │                           │
       │  FieldCondition(            │          │  Applied before ts_rank() │
       │    key="total_stars",       │          │  scoring                  │
       │    range=Range(gte=50)      │          │                           │
       │  )                          │          └───────────────────────────┘
       │  FieldCondition(            │
       │    key="location",          │
       │    match=MatchValue(        │
       │      "san francisco")       │
       │  )                          │
       │                             │
       │  Applied during HNSW scan   │
       │  (pre-filter)               │
       └─────────────────────────────┘

  Supported filters:
    ┌─────────────────────┬──────────┬─────────────────────────────────┐
    │ Filter              │ Type     │ Qdrant / Postgres               │
    ├─────────────────────┼──────────┼─────────────────────────────────┤
    │ languages           │ array    │ MatchAny / JSONB ?|             │
    │ skills              │ array    │ MatchAny / JSONB ?|             │
    │ topics              │ array    │ MatchAny / (not in keyword)     │
    │ location            │ string   │ MatchValue / lower() =          │
    │ company             │ string   │ MatchValue / lower() =          │
    │ min_stars           │ numeric  │ Range(gte) / >= compare         │
    │ min_experience_years│ numeric  │ Range(gte) / >= compare         │
    │ min_contributions   │ numeric  │ Range(gte) / >= compare         │
    │ min_followers       │ numeric  │ Range(gte) / >= compare         │
    └─────────────────────┴──────────┴─────────────────────────────────┘

  ---
  Why This Design Works at 5M+ Scale

  Component          │ 5M profiles impact          │ How we handle it
  ───────────────────┼─────────────────────────────┼──────────────────────────
  Qdrant HNSW        │ ~2GB vectors (384*4B*5M)    │ INT8 quantization → ~500MB
                     │ O(log n) search             │ always_ram=true
  ───────────────────┼─────────────────────────────┼──────────────────────────
  Postgres tsvector  │ GIN index grows with docs   │ Pre-built index, trigger
                     │ But ts_rank is cheap        │ auto-maintains on INSERT
  ───────────────────┼─────────────────────────────┼──────────────────────────
  Cross-encoder      │ Can't score 5M docs         │ Only scores top 200
                     │ ~50ms per 200 candidates    │ from fusion step
  ───────────────────┼─────────────────────────────┼──────────────────────────
  N+1 queries        │ 20 results = 40 queries     │ Batched to 2 queries
                     │ At scale: unacceptable      │ using WHERE id IN (...)
  ───────────────────┼─────────────────────────────┼──────────────────────────
  Batch embedding    │ 5M * embed() = slow         │ batch_embed_profiles()
                     │                             │ 100-per-batch, background

