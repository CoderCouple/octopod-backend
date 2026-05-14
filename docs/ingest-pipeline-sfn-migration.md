# Ingest Pipeline → AWS Step Functions migration

**Status:** Design draft — pending review
**Author:** Claude (with @sunil)
**Last updated:** 2026-05-13

## Problem

The current ingest pipeline runs **in-process inside the FastAPI container** via FastAPI `BackgroundTasks` + `asyncio.run()` (see `app/api/v1/controller/ingest_pipeline_api.py` and `app/ingest/pipeline/runner.py`). Three concrete pain points:

1. **Silent failures.** Background-task exceptions get swallowed. We hit one this week — `mode="all"` mismatch caused 0 items processed and the orchestrator exited with `success`. No alarm, no log, no observability. We only noticed because search returned empty.
2. **Deploys kill in-flight ingestion.** ECS rolling deploy stops the container; any pipeline mid-run is lost. The `mark_stale_running_as_paused` recovery on startup is a band-aid.
3. **No live visibility.** To see what step a pipeline is on, you DB-spelunk `pipeline_execution_step`. No console view, no live progress.

A fourth concern, **scale**, is anticipated but not yet hit. The current single-process orchestrator can't fan out beyond `concurrency` (default 8) async tasks, and any single ingest job is bounded by the ECS task's lifetime (no hard cap, but practically bounded by deploy cadence).

## Goals

| # | Goal | Measurable outcome |
|---|---|---|
| G1 | Background failures are loud + observable | Every step failure produces a CloudWatch event AND populates `pipeline_execution_step.error_summary` |
| G2 | In-flight pipelines survive ECS deploys | A pipeline started before a deploy completes after the deploy without manual intervention |
| G3 | Live visual pipeline view | AWS Step Functions console shows current step, in/out, retry attempts |
| G4 | Per-step retry + timeout policies | No hand-rolled retry in orchestrator code |
| G5 | (Phase 2) Per-user parallelism with safe concurrency caps | 5,000 HF users ingest in <30 min wall-clock instead of serially in 4+ hours |

## Non-goals

- Replace the orchestrator implementations themselves (`app/ingest/gh/orchestrator.py`, `hf/orchestrator.py`, `bridge/orchestrator.py`). They stay.
- Replace the DB tracking (`pipeline_execution`, `pipeline_execution_step`, `ingest_job`, `ingest_job_item`). Schema unchanged.
- Migrate the scheduler (`app/ingest/pipeline/scheduler.py`). Out of scope — separate ticket if we want to move from in-process cron to EventBridge.
- Touch the API contract for `POST /api/v1/ingest/pipeline/start`. Same request/response, different implementation underneath.

## Phased delivery

### Phase 1 — Hybrid SFN (week 1)

Step Functions orchestrates **6 high-level pipeline stages**. Each stage is a single ECS RunTask invocation that runs the existing orchestrator code via a CLI entrypoint. Internal asyncio batching inside each orchestrator is preserved.

**State machine layout:**

```
Start
  │
  ├─► gh_discover (ECS RunTask)
  │     └─ writes top-N users to gh_checkpoints
  │
  ├─► gh_ingest (ECS RunTask)
  │     └─ reads pending gh_checkpoints, writes gh_users + gh_repositories + ...
  │
  ├─► hf_discover (ECS RunTask)
  │     └─ writes top-N authors to hf_checkpoints
  │
  ├─► hf_ingest (ECS RunTask)
  │     └─ reads pending hf_checkpoints, writes hf_users + hf_models + ...
  │
  ├─► bridge_sync (ECS RunTask)
  │     └─ raw → domain → aggregated → cohesive
  │
  ├─► embed (ECS RunTask)
  │     └─ writes vectors to Qdrant + docs to OpenSearch
  │
End
```

**Branching:** existing pipeline types (`daily`, `weekly`, `seed`, `gh_only`, `hf_only`, `dependent`) map to subsets of these states using SFN `Choice` based on input parameter `pipeline_type`.

**Per-step policies:**
- Retry: 3 attempts, exponential backoff, on transient errors (HTTP 5xx, throttling, network)
- Timeout: 6 hours per step (matches RunTask default)
- Catch-all: `States.ALL` → terminal `Failed` state with the error written to DB

### Phase 2 — Distributed Map for ingestion (week 2)

Replace the single `gh_ingest` / `hf_ingest` RunTask with a **Distributed Map** that fans out batches in parallel.

```
gh_ingest:
  Map (mode=DISTRIBUTED, ItemReader=S3 manifest of pending logins)
    ConcurrencyLimit: 50
    BatchSize: 100 logins per ECS RunTask invocation
    ItemProcessor:
      ECS RunTask running:
        ingest pipeline-step gh-ingest-batch --logins '<JSON list of 100>'
```

Why batched (not one-per-user): per-user steps would mean 5000 transitions × $0.025/1k = $0.125 per pipeline (cheap), but each transition has ~500ms overhead. Batching to 100 keeps within Lambda/RunTask startup-amortization window.

### Phase 3 — Polish (optional, 3-5 days)

- CloudWatch dashboards (per-stage success rate, p50/p95 duration)
- Cost alerts ($X/month threshold)
- Runbook for common failure modes
- Parallel SFN execution support (multiple pipelines at once)

## Architecture details

### State passing between steps

SFN has a **256 KB hard limit** on the JSON state passed between states. Today the in-process runner keeps things like `self._discovered_hf_usernames` (potentially 5000+ strings) in memory. After migration:

- **Discovery output** (long lists of usernames) → written to **`hf_checkpoints` / `gh_checkpoints` DB tables** (already happens — discover writes there). Subsequent ingest step reads from DB. SFN state only carries pointers like `{"job_id": "ij_...", "platform": "hf"}`.
- **Pipeline parameters** (top, alpha, since_hours) → kept in SFN state, well under 256 KB.
- **Per-step results** (counts, durations) → written to `pipeline_execution_step` DB rows + summarized in SFN state.

For Phase 2 Distributed Map: the manifest of items to fan out across is written to S3 by the discovery step, and the Map's `ItemReader` reads it. Avoids the 256 KB limit entirely.

### CFN structure

New stack: **`infra/12-ingest-pipeline-sfn-stack/`**

```
ingest-pipeline-sfn-stack.yaml
├── Parameters
│   - ProjectName, Environment
│   - ClusterStackName, ECSStackName  (for ARN imports)
│
├── Resources
│   ├── IngestPipelineStateMachine (AWS::StepFunctions::StateMachine)
│   │     - DefinitionString from local YAML
│   │
│   ├── SFNExecutionRole (AWS::IAM::Role)
│   │     - ecs:RunTask, ecs:DescribeTasks, ecs:StopTask
│   │     - iam:PassRole on the existing ECS task role
│   │     - logs:* on its log group
│   │     - states:StartExecution (for child workflows in phase 2)
│   │
│   ├── IngestPipelineLogGroup (AWS::Logs::LogGroup)
│   │
│   └── (Phase 2) ManifestBucket (AWS::S3::Bucket)
│         - holds Distributed Map item manifests
│
└── Outputs
    ├── StateMachineArn
    └── SFNExecutionRoleArn
```

The state machine definition itself lives in the YAML as Amazon States Language (ASL).

### CLI entrypoints

`app/ingest/cli.py` already has CLI entrypoints for most steps. We need to standardize them with:
- Stable JSON I/O (read params from env or argv, write result to stdout last line as JSON)
- Exit codes: `0` = success, `1` = transient error (SFN retries), `2` = permanent error (SFN fails)

Concrete commands SFN will run via `ecs:RunTask` (using a single task definition, just different `containerOverrides.command`):

```bash
python -m app.ingest.cli pipeline-step gh-discover --top 5000 --alpha 0.5
python -m app.ingest.cli pipeline-step gh-ingest --concurrency 8
python -m app.ingest.cli pipeline-step hf-discover --top 5000 --alpha 0.5
python -m app.ingest.cli pipeline-step hf-ingest --concurrency 8
python -m app.ingest.cli pipeline-step bridge-sync --mode full --since-hours 48
python -m app.ingest.cli pipeline-step embed --batch-size 200 --include-opensearch
```

Each writes its own `ingest_job` row, populates `ingest_job_item` rows, and updates `pipeline_execution_step` (linking to SFN execution ARN as `pipeline_execution.id`).

### API endpoint changes

`POST /api/v1/ingest/pipeline/start` — same contract, new internals:

```python
# before
background_tasks.add_task(lambda: asyncio.run(_run()))

# after
sfn = boto3.client("stepfunctions", region_name=settings.aws_region)
resp = sfn.start_execution(
    stateMachineArn=settings.sfn_pipeline_arn,
    input=json.dumps({
        "pipeline_type": req.pipeline_type,
        "input_params": req.input_params or {},
    }),
)
execution_arn = resp["executionArn"]
# create pipeline_execution row with id = execution_arn (truncated to fit)
```

`GET /api/v1/ingest/pipeline/{execution_id}` — reads `pipeline_execution` like today, also calls `sfn.describe_execution()` for live SFN status if requested.

`POST /api/v1/ingest/pipeline/{execution_id}/pause|resume|cancel` — translates to SFN API calls (`stop_execution` for cancel; pause/resume requires custom Wait state design — defer to Phase 3).

### Migration strategy

**Option A: Cutover (recommended for dev).** Deploy SFN stack. Switch the API endpoint to use SFN. Delete the old runner. Done in one PR.

**Option B: Parallel run.** Add a feature flag `INGEST_USE_SFN`. New pipelines triggered while flag is true go through SFN; flag false → old runner. Verify equivalence on a few runs, then flip default. Delete old runner after a week of soak.

For a dev environment with one user, **Option A is fine**. For a prod environment with paying customers, do Option B.

### Rollback plan

Old `app/ingest/pipeline/runner.py` is preserved in git history. To rollback:
1. Revert the API endpoint change (single commit revert)
2. Redeploy
3. SFN state machine stays registered but unused (no cost when idle)

If we delete `runner.py` in the same PR, rollback requires a `git revert` of the deletion commit too.

### Observability

| Signal | Today | After SFN |
|---|---|---|
| Pipeline started | DB row in `pipeline_execution` | DB row + SFN execution started event |
| Step started | DB row in `pipeline_execution_step` | Same + SFN state entered event |
| Step failed | If we caught the exception: DB row updated. If not: silent. | Always SFN state failure event → CloudWatch + DB |
| Pipeline completed | DB row updated by orchestrator | Same + SFN execution succeeded event |
| Live progress | Refresh DB query | AWS Console graph view + DB |

## Cost estimate

Steady state (1 daily pipeline run, 5,000 users):

| Component | Cost |
|---|---|
| SFN state transitions (Phase 1: ~10 transitions/run) | ~$0.0003/run |
| SFN state transitions (Phase 2 Map: ~150 transitions/run) | ~$0.004/run |
| ECS RunTask (already running, just invoked differently) | $0 incremental |
| CloudWatch Logs from SFN | <$0.01/run |
| **Total per daily pipeline** | **<$0.02/run = <$0.60/month** |

Negligible.

## Code change estimate

| File | Type | Approx LOC |
|---|---|---|
| `infra/12-ingest-pipeline-sfn-stack/sfn-stack.yaml` | new | ~250 (mostly state machine ASL) |
| `infra/12-ingest-pipeline-sfn-stack/sfn-stack-params.json` | new | ~30 |
| `app/ingest/cli.py` — standardize CLI entrypoints | modified | ~150 (add stable JSON I/O, exit codes) |
| `app/api/v1/controller/ingest_pipeline_api.py` — replace background_tasks with SFN | modified | ~80 |
| `app/settings.py` — add `sfn_pipeline_arn` | modified | ~5 |
| `app/ingest/pipeline/runner.py` | **deleted** | -560 |
| `tests/test_api/test_pipeline.py` | modified | ~50 |
| Total | | **~+500, -560** net reduction |

## Open questions

1. **Pause/resume semantics.** Today users can pause a running pipeline via DB `control_signal`. SFN doesn't natively support pause — only stop. For Phase 1, pause = "no longer supported"? Or implement as Wait state polling DB? Need product decision.
2. **Per-user retry.** Today a failed user is recorded in `ingest_job_item` and can be retried via `/ingest/retry`. With Distributed Map, individual item failures are handled by Map's retry policy. Do we keep `/ingest/retry` for items that exhausted SFN retries?
3. **Scheduler.** Today `app/ingest/pipeline/scheduler.py` runs cron-style schedules in-process. Should it also be migrated to EventBridge Scheduler → SFN, or stay in-process? (Out of scope for this doc but worth flagging.)
4. **Local development.** SFN is hard to test locally. Do we run a Step Functions Local docker container, or accept that pipeline tests run against a deployed dev SFN stack?

## Approval needed before implementing

- [ ] Approve phased delivery (Phase 1 first, decide on Phase 2 after measuring)
- [ ] Approve Option A cutover (or require Option B parallel run)
- [ ] Resolve pause/resume question
- [ ] Resolve local dev question
