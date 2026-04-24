╭─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Plan to implement                                                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ Plan: Split ingest_api.py into 5 focused controllers                                                                                                                                                │
│                                                                                                                                                                                                     │
│ Context                                                                                                                                                                                             │
│                                                                                                                                                                                                     │
│ ingest_api.py has grown to ~1800 lines / 33 endpoints covering 9 different concerns. The email system already follows the right pattern — 5 small controllers (mailbox_api.py,                      │
│ email_campaign_api.py, email_template_api.py, email_tracking_api.py, email_enrichment_api.py). We replicate that pattern for ingest.                                                                │
│                                                                                                                                                                                                     │
│ No URL changes — all endpoints keep their existing /api/v1/ingest/... paths. This is a pure code-organization refactor.                                                                             │
│                                                                                                                                                                                                     │
│ New File Layout                                                                                                                                                                                     │
│                                                                                                                                                                                                     │
│ ┌────────────────────────┬────────────────────────────────────────────────────────────────────────────┬──────────────┐                                                                              │
│ │        New File        │                                 Endpoints                                  │ Source Lines │                                                                              │
│ ├────────────────────────┼────────────────────────────────────────────────────────────────────────────┼──────────────┤                                                                              │
│ │ ingest_source_api.py   │ GH/HF/LN discover + run (6)                                                │ ~430         │                                                                              │
│ ├────────────────────────┼────────────────────────────────────────────────────────────────────────────┼──────────────┤                                                                              │
│ │ ingest_job_api.py      │ jobs list/detail/items/data, status, retry (7)                             │ ~380         │                                                                              │
│ ├────────────────────────┼────────────────────────────────────────────────────────────────────────────┼──────────────┤                                                                              │
│ │ ingest_pipeline_api.py │ pipeline start/pause/resume/cancel/rerun/active/status + sync + embed (10) │ ~430         │                                                                              │
│ ├────────────────────────┼────────────────────────────────────────────────────────────────────────────┼──────────────┤                                                                              │
│ │ ingest_schedule_api.py │ schedule CRUD (4)                                                          │ ~185         │                                                                              │
│ ├────────────────────────┼────────────────────────────────────────────────────────────────────────────┼──────────────┤                                                                              │
│ │ ingest_identity_api.py │ identity candidates/approve/reject/resolve/stats (6)                       │ ~280         │                                                                              │
│ └────────────────────────┴────────────────────────────────────────────────────────────────────────────┴──────────────┘                                                                              │
│                                                                                                                                                                                                     │
│ Shared code extracted to: app/api/v1/controller/ingest_common.py                                                                                                                                    │
│                                                                                                                                                                                                     │
│ 1. Shared Module — NEW app/api/v1/controller/ingest_common.py                                                                                                                                       │
│                                                                                                                                                                                                     │
│ Extract these from ingest_api.py:                                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ # Helper used by job_api, identity_api, pipeline_api                                                                                                                                                │
│ def _serialize_row(row: dict[str, Any]) -> dict[str, Any]                                                                                                                                           │
│                                                                                                                                                                                                     │
│ # Helpers used by job_api only, but extracted for cleanliness                                                                                                                                       │
│ async def _fetch_gh_user_data(conn, login) -> dict[str, Any]                                                                                                                                        │
│ async def _fetch_hf_user_data(conn, username) -> dict[str, Any]                                                                                                                                     │
│                                                                                                                                                                                                     │
│ Request models stay in their respective controller files since none are shared across controllers:                                                                                                  │
│ - DiscoverRequest → ingest_source_api.py                                                                                                                                                            │
│ - IngestRequest → ingest_source_api.py                                                                                                                                                              │
│ - LNIngestRequest → ingest_source_api.py                                                                                                                                                            │
│ - RetryRequest → ingest_job_api.py                                                                                                                                                                  │
│ - SyncRequest → ingest_pipeline_api.py                                                                                                                                                              │
│ - EmbedRequest → ingest_pipeline_api.py                                                                                                                                                             │
│ - PipelineStartRequest → ingest_pipeline_api.py                                                                                                                                                     │
│ - ScheduleCreateRequest, ScheduleUpdateRequest → ingest_schedule_api.py                                                                                                                             │
│ - IdentityResolveRequest → ingest_identity_api.py                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ 2. ingest_source_api.py — Discovery + Ingestion                                                                                                                                                     │
│                                                                                                                                                                                                     │
│ router = APIRouter(prefix="/ingest", tags=[Tags.Ingestion])                                                                                                                                         │
│                                                                                                                                                                                                     │
│ Endpoints moved here:                                                                                                                                                                               │
│ - POST /gh/discover — discover top GH users                                                                                                                                                         │
│ - POST /gh/run — ingest GH profiles                                                                                                                                                                 │
│ - POST /hf/discover — discover top HF authors                                                                                                                                                       │
│ - POST /hf/run — ingest HF profiles                                                                                                                                                                 │
│ - POST /ln/discover — extract LinkedIn URLs                                                                                                                                                         │
│ - POST /ln/run — ingest LinkedIn profiles                                                                                                                                                           │
│                                                                                                                                                                                                     │
│ Request models: DiscoverRequest, IngestRequest, LNIngestRequest                                                                                                                                     │
│                                                                                                                                                                                                     │
│ 3. ingest_job_api.py — Job Monitoring & Retry                                                                                                                                                       │
│                                                                                                                                                                                                     │
│ router = APIRouter(prefix="/ingest", tags=[Tags.Ingestion])                                                                                                                                         │
│                                                                                                                                                                                                     │
│ Endpoints moved here:                                                                                                                                                                               │
│ - GET /status — checkpoint summary                                                                                                                                                                  │
│ - POST /retry — retry failed ingestions                                                                                                                                                             │
│ - GET /jobs — list jobs (filters: job_type, platform, status, limit, offset)                                                                                                                        │
│ - GET /jobs/{job_id} — job detail + counts                                                                                                                                                          │
│ - GET /jobs/{job_id}/items — job items list                                                                                                                                                         │
│ - GET /jobs/{job_id}/data — ingested data for job                                                                                                                                                   │
│ - GET /jobs/{job_id}/data/{login} — single user data                                                                                                                                                │
│                                                                                                                                                                                                     │
│ Imports from ingest_common: _serialize_row, _fetch_gh_user_data, _fetch_hf_user_data                                                                                                                │
│ Request models: RetryRequest                                                                                                                                                                        │
│                                                                                                                                                                                                     │
│ 4. ingest_pipeline_api.py — Pipeline + Sync + Embed                                                                                                                                                 │
│                                                                                                                                                                                                     │
│ router = APIRouter(prefix="/ingest", tags=[Tags.Ingestion])                                                                                                                                         │
│                                                                                                                                                                                                     │
│ Endpoints moved here:                                                                                                                                                                               │
│ - POST /sync — trigger bridge sync                                                                                                                                                                  │
│ - POST /embed — trigger batch embedding                                                                                                                                                             │
│ - POST /pipeline/start — start pipeline                                                                                                                                                             │
│ - GET /pipeline/active — list active                                                                                                                                                                │
│ - GET /pipeline/{execution_id} — execution detail                                                                                                                                                   │
│ - POST /pipeline/{execution_id}/pause                                                                                                                                                               │
│ - POST /pipeline/{execution_id}/resume                                                                                                                                                              │
│ - POST /pipeline/{execution_id}/cancel                                                                                                                                                              │
│ - POST /pipeline/{execution_id}/rerun                                                                                                                                                               │
│ - GET /pipeline/status — health dashboard                                                                                                                                                           │
│                                                                                                                                                                                                     │
│ Also moves: _run_embed() async helper, _FULL_PIPELINE_TYPES constant                                                                                                                                │
│ Imports from ingest_common: _serialize_row                                                                                                                                                          │
│ Request models: SyncRequest, EmbedRequest, PipelineStartRequest                                                                                                                                     │
│                                                                                                                                                                                                     │
│ 5. ingest_schedule_api.py — Schedule CRUD                                                                                                                                                           │
│                                                                                                                                                                                                     │
│ router = APIRouter(prefix="/ingest", tags=[Tags.Ingestion])                                                                                                                                         │
│                                                                                                                                                                                                     │
│ Endpoints moved here:                                                                                                                                                                               │
│ - POST /schedule — create schedule                                                                                                                                                                  │
│ - GET /schedules — list schedules                                                                                                                                                                   │
│ - PUT /schedule/{schedule_id} — update schedule                                                                                                                                                     │
│ - DELETE /schedule/{schedule_id} — delete schedule                                                                                                                                                  │
│                                                                                                                                                                                                     │
│ Imports from ingest_common: _serialize_row                                                                                                                                                          │
│ Request models: ScheduleCreateRequest, ScheduleUpdateRequest                                                                                                                                        │
│                                                                                                                                                                                                     │
│ 6. ingest_identity_api.py — Identity Resolution                                                                                                                                                     │
│                                                                                                                                                                                                     │
│ router = APIRouter(prefix="/ingest", tags=[Tags.Ingestion])                                                                                                                                         │
│                                                                                                                                                                                                     │
│ Endpoints moved here:                                                                                                                                                                               │
│ - GET /identity/candidates — list merge candidates                                                                                                                                                  │
│ - GET /identity/candidates/{candidate_id} — candidate detail                                                                                                                                        │
│ - POST /identity/candidates/{candidate_id}/approve — approve + merge                                                                                                                                │
│ - POST /identity/candidates/{candidate_id}/reject — reject                                                                                                                                          │
│ - POST /identity/resolve — trigger resolution                                                                                                                                                       │
│ - GET /identity/stats — resolution stats                                                                                                                                                            │
│                                                                                                                                                                                                     │
│ Imports from ingest_common: _serialize_row                                                                                                                                                          │
│ Request models: IdentityResolveRequest                                                                                                                                                              │
│                                                                                                                                                                                                     │
│ 7. Router Registration — app/api/v1/router.py                                                                                                                                                       │
│                                                                                                                                                                                                     │
│ Replace single ingest_router import with 5 imports:                                                                                                                                                 │
│                                                                                                                                                                                                     │
│ from app.api.v1.controller.ingest_source_api import router as ingest_source_router                                                                                                                  │
│ from app.api.v1.controller.ingest_job_api import router as ingest_job_router                                                                                                                        │
│ from app.api.v1.controller.ingest_pipeline_api import router as ingest_pipeline_router                                                                                                              │
│ from app.api.v1.controller.ingest_schedule_api import router as ingest_schedule_router                                                                                                              │
│ from app.api.v1.controller.ingest_identity_api import router as ingest_identity_router                                                                                                              │
│                                                                                                                                                                                                     │
│ router.include_router(ingest_source_router)                                                                                                                                                         │
│ router.include_router(ingest_job_router)                                                                                                                                                            │
│ router.include_router(ingest_pipeline_router)                                                                                                                                                       │
│ router.include_router(ingest_schedule_router)                                                                                                                                                       │
│ router.include_router(ingest_identity_router)                                                                                                                                                       │
│                                                                                                                                                                                                     │
│ 8. Delete ingest_api.py                                                                                                                                                                             │
│                                                                                                                                                                                                     │
│ After all endpoints are moved and verified, delete the original file.                                                                                                                               │
│                                                                                                                                                                                                     │
│ Implementation Order                                                                                                                                                                                │
│                                                                                                                                                                                                     │
│ 1. Create ingest_common.py (shared helpers)                                                                                                                                                         │
│ 2. Create ingest_source_api.py (GH/HF/LN discover + run)                                                                                                                                            │
│ 3. Create ingest_job_api.py (jobs + status + retry)                                                                                                                                                 │
│ 4. Create ingest_pipeline_api.py (pipeline + sync + embed)                                                                                                                                          │
│ 5. Create ingest_schedule_api.py (schedule CRUD)                                                                                                                                                    │
│ 6. Create ingest_identity_api.py (identity resolution)                                                                                                                                              │
│ 7. Update app/api/v1/router.py — replace single import with 5                                                                                                                                       │
│ 8. Delete ingest_api.py                                                                                                                                                                             │
│ 9. make lint — verify no errors                                                                                                                                                                     │
│                                                                                                                                                                                                     │
│ Files Changed                                                                                                                                                                                       │
│                                                                                                                                                                                                     │
│ ┌──────────────────────────────────────────────┬────────────────────────────────┐                                                                                                                   │
│ │                     File                     │             Action             │                                                                                                                   │
│ ├──────────────────────────────────────────────┼────────────────────────────────┤                                                                                                                   │
│ │ app/api/v1/controller/ingest_common.py       │ NEW — shared helpers           │                                                                                                                   │
│ ├──────────────────────────────────────────────┼────────────────────────────────┤                                                                                                                   │
│ │ app/api/v1/controller/ingest_source_api.py   │ NEW — 6 endpoints              │                                                                                                                   │
│ ├──────────────────────────────────────────────┼────────────────────────────────┤                                                                                                                   │
│ │ app/api/v1/controller/ingest_job_api.py      │ NEW — 7 endpoints              │                                                                                                                   │
│ ├──────────────────────────────────────────────┼────────────────────────────────┤                                                                                                                   │
│ │ app/api/v1/controller/ingest_pipeline_api.py │ NEW — 10 endpoints             │                                                                                                                   │
│ ├──────────────────────────────────────────────┼────────────────────────────────┤                                                                                                                   │
│ │ app/api/v1/controller/ingest_schedule_api.py │ NEW — 4 endpoints              │                                                                                                                   │
│ ├──────────────────────────────────────────────┼────────────────────────────────┤                                                                                                                   │
│ │ app/api/v1/controller/ingest_identity_api.py │ NEW — 6 endpoints              │                                                                                                                   │
│ ├──────────────────────────────────────────────┼────────────────────────────────┤                                                                                                                   │
│ │ app/api/v1/router.py                         │ Update imports (1 → 5 routers) │                                                                                                                   │
│ ├──────────────────────────────────────────────┼────────────────────────────────┤                                                                                                                   │
│ │ app/api/v1/controller/ingest_api.py          │ DELETE                         │                                                                                                                   │
│ └──────────────────────────────────────────────┴────────────────────────────────┘                                                                                                                   │
│                                                                                                                                                                                                     │
│ Verification                                                                                                                                                                                        │
│                                                                                                                                                                                                     │
│ 1. make lint — no errors                                                                                                                                                                            │
│ 2. Swagger UI (/docs) — all 33 endpoints still appear under "Ingestion" tag                                                                                                                         │
│ 3. All existing endpoint URLs unchanged (/api/v1/ingest/...)                                                                                                                                        │
│ 4. No circular imports between the 5 controllers + common                                                                                                                                           │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
