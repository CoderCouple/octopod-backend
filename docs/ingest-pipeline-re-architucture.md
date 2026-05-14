 Difficulty: Medium, ~1-2 weeks

  The current pipeline is well-structured: each step is already a method (_step_gh_discover, _step_hf_ingest, etc.) with clear inputs/outputs. The hard part is state passing — today the steps share in-memory state (self._discovered_hf_usernames), which can't survive a Step Functions boundary.

  Pros

  ┌───────────────────────────────────────────────────────┬────────────────────────────────────────────────────────────────────────────────────────┐
  │                          Win                          │                                  Why it matters here                                   │
  ├───────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
  │ No more BackgroundTasks + asyncio.run silent failures │ We literally just hit this — the mode="all" bug was invisible because nothing logs     │
  ├───────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
  │ Workflows survive deploys/restarts                    │ Today, redeploying ECS kills any in-flight ingest                                      │
  ├───────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
  │ Built-in retry, timeout, exponential backoff per step │ Currently hand-rolled in each orchestrator                                             │
  ├───────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
  │ Visual pipeline in AWS Console                        │ DB-only progress tracking is painful to debug                                          │
  ├───────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
  │ Native pause/resume via SFN, not DB polling           │ Today it's a control_signal column the worker checks every iteration                   │
  ├───────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
  │ Distributed Map for the ingest steps                  │ 5,000 users could run as 5,000 parallel mini-executions with built-in concurrency caps │
  ├───────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
  │ No 6-hour ECS task limits                             │ A full daily run hits this today                                                       │
  └───────────────────────────────────────────────────────┴────────────────────────────────────────────────────────────────────────────────────────┘

  Cons

  ┌─────────────────────────────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │              Pain               │                                                                                           Severity                                                                                           │
  ├─────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 256KB state limit between steps │ Big one — can't pass [username]*5000 between steps. Need to materialize to S3 or DB.                                                                                                         │
  ├─────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Cost: $0.025 per 1k transitions │ Daily pipeline with 5k users in Map = ~50k transitions ≈ $1.25/run. Adds up.                                                                                                                 │
  ├─────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Lambda 15-min timeout           │ If any step (HF ingest of all users) needs to be a single Lambda, it won't fit. Need ECS-task-as-step ("RunTask").                                                                           │
  ├─────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Local dev pain                  │ Step Functions Local Docker image exists but is clunky. Slows iteration.                                                                                                                     │
  ├─────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ More refactor than it looks     │ The asyncio batching/worker-pool in gh/orchestrator.py is doing meaningful work — splitting that into "one user per step" loses efficiency unless you Distributed Map with batch size 50-100 │
  ├─────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ AWS lock-in                     │ If you ever want to run locally or on another cloud, harder                                                                                                                                  │
  └─────────────────────────────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

  Recommended path

  Hybrid: SFN orchestrates, ECS tasks execute. Don't decompose to per-user-as-step. Instead:

  StateMachine:
    Step 1: ECS RunTask → run gh_discover orchestrator → writes to gh_checkpoints
    Step 2: ECS RunTask → run gh_ingest orchestrator   → reads checkpoints, writes gh_users
    Step 3: ECS RunTask → run hf_discover orchestrator
    Step 4: ECS RunTask → run hf_ingest orchestrator
    Step 5: ECS RunTask → bridge_sync orchestrator
    Step 6: ECS RunTask → embed orchestrator

  Each step is the existing orchestrator code wrapped in a thin CLI entrypoint (you already have app/ingest/cli.py). SFN handles retry/timeout/branching; DB stays the source of truth for what was processed.

  What you'd write:
  1. Bridge entrypoints in cli.py so each step runs as python -m app.ingest.cli pipeline-step gh_discover --params '...' (you have most of these)
  2. CloudFormation stack 12-ingest-pipeline-stepfunctions/ with the state machine def
  3. IAM role for SFN to call ECS RunTask
  4. Delete the existing app/ingest/pipeline/runner.py orchestrator (the in-process one)
  5. Keep the pipeline_execution DB tracking, but populate it from the SFN context (execution ARN as id)

  What you'd NOT touch:
  - The orchestrator implementations themselves (gh/orchestrator.py, etc.) — those are fine
  - The job_tracker / DB schema — those still work
  - API endpoints like /ingest/pipeline/start — they just kick off an SFN execution instead of a background task

  Alternative if SFN feels heavy

  SQS + Lambda for the trivial fan-out steps, keep current orchestrator for the heavy lifting. Costs less, less AWS-specific magic, but doesn't solve the "deploy kills running pipeline" problem.

  My pragmatic take

  If you're seeing real pain (BackgroundTasks silent failures, ingestion killed by ECS deploys, no visibility), yes, migrate. The hybrid approach is ~1 week of focused work and pays off operationally.

  If the only pain is the bug we just hit (mode mismatch), just fix the bugs in the current system. Add structured logging, make BackgroundTasks raise on errors, validate the mode enum at the request schema layer.

  Want me to sketch the hybrid SFN stack (template file structure + the new CLI entrypoints needed) as a follow-up after we finish the search test?