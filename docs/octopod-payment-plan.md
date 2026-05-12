╭─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Plan to implement                                                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ Stripe Payment/Subscription Feature — Design Decisions & Implementation Plan                                                                                                                        │
│                                                                                                                                                                                                     │
│ Context                                                                                                                                                                                             │
│                                                                                                                                                                                                     │
│ Multi-tenant system (Org → User → Project) is already implemented. We need to add Stripe-based subscription billing:                                                                                │
│ - Per-seat pricing: plan tier × member count                                                                                                                                                        │
│ - Org-level billing: personal orgs = individual plans, team orgs = team plans                                                                                                                       │
│ - Plan limits: emails/month, mailboxes, campaigns, profiles, ingestion jobs, enrichment calls, projects, members                                                                                    │
│ - Personal→team conversion: when user adds first team member, personal plan auto-upgrades                                                                                                           │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ Key Design Decisions — Pros & Cons                                                                                                                                                                  │
│                                                                                                                                                                                                     │
│ 1. Subscription Data: Separate Table vs Columns on Organization                                                                                                                                     │
│                                                                                                                                                                                                     │
│ Option A: Separate subscription table (1:1 with org) ← RECOMMENDED                                                                                                                                  │
│                                                                                                                                                                                                     │
│ ┌───────────────────────────────────────────────────────────────────────────────┬─────────────────────────────────────────────────────────────────┐                                                 │
│ │                                     Pros                                      │                              Cons                               │                                                 │
│ ├───────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤                                                 │
│ │ Clean separation of concerns — billing doesn't pollute org model              │ Extra JOIN when you need plan + org data together               │                                                 │
│ ├───────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤                                                 │
│ │ Can store full Stripe state (period dates, cancel flags) without bloating org │ Slight duplication of plan field (org.plan + subscription.plan) │                                                 │
│ ├───────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤                                                 │
│ │ Easier to add billing features later (trials, coupons, invoices)              │ Must keep org.plan and subscription.plan in sync                │                                                 │
│ ├───────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤                                                 │
│ │ Can soft-delete subscription without touching org                             │ One more table to manage                                        │                                                 │
│ ├───────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤                                                 │
│ │ Standard SaaS pattern (Stripe's own docs recommend it)                        │                                                                 │                                                 │
│ └───────────────────────────────────────────────────────────────────────────────┴─────────────────────────────────────────────────────────────────┘                                                 │
│                                                                                                                                                                                                     │
│ Option B: Add Stripe columns directly to organization table                                                                                                                                         │
│                                                                                                                                                                                                     │
│ ┌────────────────────────────────────────┬───────────────────────────────────────────────────┐                                                                                                      │
│ │                  Pros                  │                       Cons                        │                                                                                                      │
│ ├────────────────────────────────────────┼───────────────────────────────────────────────────┤                                                                                                      │
│ │ No JOIN needed — all data in one place │ Org model becomes bloated with 8+ billing columns │                                                                                                      │
│ ├────────────────────────────────────────┼───────────────────────────────────────────────────┤                                                                                                      │
│ │ No sync issue — single source of truth │ Harder to add billing features later              │                                                                                                      │
│ ├────────────────────────────────────────┼───────────────────────────────────────────────────┤                                                                                                      │
│ │ Simpler queries                        │ Mixes two concerns (org management + billing)     │                                                                                                      │
│ ├────────────────────────────────────────┼───────────────────────────────────────────────────┤                                                                                                      │
│ │                                        │ Harder to test billing in isolation               │                                                                                                      │
│ └────────────────────────────────────────┴───────────────────────────────────────────────────┘                                                                                                      │
│                                                                                                                                                                                                     │
│ Verdict: Option A. The extra table is a small cost for clean separation, and Stripe integrations always grow over time.                                                                             │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ 2. Plan Limits: Code (dataclass) vs DB Table vs Config File                                                                                                                                         │
│                                                                                                                                                                                                     │
│ Option A: Frozen dataclass in code ← RECOMMENDED                                                                                                                                                    │
│                                                                                                                                                                                                     │
│ ┌──────────────────────────────────────────┬────────────────────────────────────────┐                                                                                                               │
│ │                   Pros                   │                  Cons                  │                                                                                                               │
│ ├──────────────────────────────────────────┼────────────────────────────────────────┤                                                                                                               │
│ │ Zero latency — no DB/file read needed    │ Requires code deploy to change limits  │                                                                                                               │
│ ├──────────────────────────────────────────┼────────────────────────────────────────┤                                                                                                               │
│ │ Type-safe, IDE autocomplete              │ Can't change limits for a specific org │                                                                                                               │
│ ├──────────────────────────────────────────┼────────────────────────────────────────┤                                                                                                               │
│ │ Easy to test — just import and assert    │ No admin UI to adjust                  │                                                                                                               │
│ ├──────────────────────────────────────────┼────────────────────────────────────────┤                                                                                                               │
│ │ Version-controlled with code             │                                        │                                                                                                               │
│ ├──────────────────────────────────────────┼────────────────────────────────────────┤                                                                                                               │
│ │ No migration needed to add/change limits │                                        │                                                                                                               │
│ └──────────────────────────────────────────┴────────────────────────────────────────┘                                                                                                               │
│                                                                                                                                                                                                     │
│ Option B: DB table (plan_config)                                                                                                                                                                    │
│                                                                                                                                                                                                     │
│ ┌──────────────────────────────┬───────────────────────────────────────────────────────┐                                                                                                            │
│ │             Pros             │                         Cons                          │                                                                                                            │
│ ├──────────────────────────────┼───────────────────────────────────────────────────────┤                                                                                                            │
│ │ Change limits without deploy │ Extra DB query on every limit check (or cache layer)  │                                                                                                            │
│ ├──────────────────────────────┼───────────────────────────────────────────────────────┤                                                                                                            │
│ │ Can override per-org         │ Need migration to seed data                           │                                                                                                            │
│ ├──────────────────────────────┼───────────────────────────────────────────────────────┤                                                                                                            │
│ │ Admin UI possible            │ More complex code — must handle missing rows, caching │                                                                                                            │
│ ├──────────────────────────────┼───────────────────────────────────────────────────────┤                                                                                                            │
│ │                              │ Cache invalidation complexity                         │                                                                                                            │
│ └──────────────────────────────┴───────────────────────────────────────────────────────┘                                                                                                            │
│                                                                                                                                                                                                     │
│ Option C: Config file (JSON/YAML)                                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ ┌────────────────────────────┬───────────────────────────────────────────────┐                                                                                                                      │
│ │            Pros            │                     Cons                      │                                                                                                                      │
│ ├────────────────────────────┼───────────────────────────────────────────────┤                                                                                                                      │
│ │ Change without code change │ Still needs deploy/restart to pick up changes │                                                                                                                      │
│ ├────────────────────────────┼───────────────────────────────────────────────┤                                                                                                                      │
│ │ Human-readable             │ No type safety                                │                                                                                                                      │
│ ├────────────────────────────┼───────────────────────────────────────────────┤                                                                                                                      │
│ │                            │ No per-org overrides                          │                                                                                                                      │
│ ├────────────────────────────┼───────────────────────────────────────────────┤                                                                                                                      │
│ │                            │ Parsing overhead                              │                                                                                                                      │
│ └────────────────────────────┴───────────────────────────────────────────────┘                                                                                                                      │
│                                                                                                                                                                                                     │
│ Verdict: Option A for now. You only have 3 plans (free/pro/enterprise) — changing limits is a deliberate business decision that should go through code review anyway. If you later need per-org     │
│ overrides, add a plan_override column on org.                                                                                                                                                       │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ 3. Enforcement: Service-Level vs Middleware                                                                                                                                                         │
│                                                                                                                                                                                                     │
│ Option A: Service-level checks ← RECOMMENDED                                                                                                                                                        │
│                                                                                                                                                                                                     │
│ ┌─────────────────────────────────────────────────────────────┬────────────────────────────────────────────────────┐                                                                                │
│ │                            Pros                             │                        Cons                        │                                                                                │
│ ├─────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────┤                                                                                │
│ │ Granular — different limits for different resources         │ Must remember to add check in every service method │                                                                                │
│ ├─────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────┤                                                                                │
│ │ Close to business logic — easy to understand                │ Slightly more code per service                     │                                                                                │
│ ├─────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────┤                                                                                │
│ │ Easy to test in isolation                                   │                                                    │                                                                                │
│ ├─────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────┤                                                                                │
│ │ Can return specific error (which limit, current count, max) │                                                    │                                                                                │
│ ├─────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────┤                                                                                │
│ │ Only runs when actually creating something                  │                                                    │                                                                                │
│ └─────────────────────────────────────────────────────────────┴────────────────────────────────────────────────────┘                                                                                │
│                                                                                                                                                                                                     │
│ Option B: Middleware-based enforcement                                                                                                                                                              │
│                                                                                                                                                                                                     │
│ ┌─────────────────────────────┬───────────────────────────────────────────────────────────────────────┐                                                                                             │
│ │            Pros             │                                 Cons                                  │                                                                                             │
│ ├─────────────────────────────┼───────────────────────────────────────────────────────────────────────┤                                                                                             │
│ │ One place to add all checks │ Too coarse — can't distinguish "create mailbox" from "list mailboxes" │                                                                                             │
│ ├─────────────────────────────┼───────────────────────────────────────────────────────────────────────┤                                                                                             │
│ │ Can't accidentally forget   │ Must parse request body in middleware to determine resource type      │                                                                                             │
│ ├─────────────────────────────┼───────────────────────────────────────────────────────────────────────┤                                                                                             │
│ │                             │ Hard to get resource-specific counts                                  │                                                                                             │
│ ├─────────────────────────────┼───────────────────────────────────────────────────────────────────────┤                                                                                             │
│ │                             │ Runs on every request (even reads)                                    │                                                                                             │
│ ├─────────────────────────────┼───────────────────────────────────────────────────────────────────────┤                                                                                             │
│ │                             │ Error messages are generic                                            │                                                                                             │
│ └─────────────────────────────┴───────────────────────────────────────────────────────────────────────┘                                                                                             │
│                                                                                                                                                                                                     │
│ Verdict: Option A. Middleware can't know whether a POST creates a mailbox or connects SMTP — only the service knows what resource is being created.                                                 │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ 4. Stripe Integration: Checkout (redirect) vs Elements (embedded)                                                                                                                                   │
│                                                                                                                                                                                                     │
│ Option A: Stripe Checkout (redirect to Stripe-hosted page) ← RECOMMENDED                                                                                                                            │
│                                                                                                                                                                                                     │
│ ┌──────────────────────────────────────────────────────┬──────────────────────────────────┐                                                                                                         │
│ │                         Pros                         │               Cons               │                                                                                                         │
│ ├──────────────────────────────────────────────────────┼──────────────────────────────────┤                                                                                                         │
│ │ Zero frontend work — Stripe handles the entire UI    │ User leaves your app temporarily │                                                                                                         │
│ ├──────────────────────────────────────────────────────┼──────────────────────────────────┤                                                                                                         │
│ │ PCI compliant out of the box                         │ Less control over look & feel    │                                                                                                         │
│ ├──────────────────────────────────────────────────────┼──────────────────────────────────┤                                                                                                         │
│ │ Stripe handles all edge cases (3DS, retries, errors) │                                  │                                                                                                         │
│ ├──────────────────────────────────────────────────────┼──────────────────────────────────┤                                                                                                         │
│ │ Supports 100+ payment methods automatically          │                                  │                                                                                                         │
│ ├──────────────────────────────────────────────────────┼──────────────────────────────────┤                                                                                                         │
│ │ 5 lines of backend code to set up                    │                                  │                                                                                                         │
│ └──────────────────────────────────────────────────────┴──────────────────────────────────┘                                                                                                         │
│                                                                                                                                                                                                     │
│ Option B: Stripe Elements (embed in your app)                                                                                                                                                       │
│                                                                                                                                                                                                     │
│ ┌────────────────────────┬───────────────────────────────────────────────┐                                                                                                                          │
│ │          Pros          │                     Cons                      │                                                                                                                          │
│ ├────────────────────────┼───────────────────────────────────────────────┤                                                                                                                          │
│ │ User stays in your app │ Significant frontend work (React components)  │                                                                                                                          │
│ ├────────────────────────┼───────────────────────────────────────────────┤                                                                                                                          │
│ │ Full control over UI   │ Must handle PCI compliance yourself           │                                                                                                                          │
│ ├────────────────────────┼───────────────────────────────────────────────┤                                                                                                                          │
│ │                        │ Must handle 3DS, errors, retries in your code │                                                                                                                          │
│ ├────────────────────────┼───────────────────────────────────────────────┤                                                                                                                          │
│ │                        │ More Stripe API calls to manage               │                                                                                                                          │
│ └────────────────────────┴───────────────────────────────────────────────┘                                                                                                                          │
│                                                                                                                                                                                                     │
│ Verdict: Option A. At this stage, Checkout is overwhelmingly better. You get a production-ready payment flow with almost no code. Switch to Elements later if you need custom checkout UX.          │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ 5. Stripe SDK: Sync calls vs Async wrappers                                                                                                                                                         │
│                                                                                                                                                                                                     │
│ Option A: Sync Stripe SDK calls wrapped in async methods ← RECOMMENDED                                                                                                                              │
│                                                                                                                                                                                                     │
│ ┌─────────────────────────────────────────────────────────┬──────────────────────────────────────────────────────┐                                                                                  │
│ │                          Pros                           │                         Cons                         │                                                                                  │
│ ├─────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤                                                                                  │
│ │ Stripe's official SDK is sync — no fighting the library │ Blocks a thread in FastAPI's threadpool              │                                                                                  │
│ ├─────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤                                                                                  │
│ │ Simple, well-documented                                 │ Under very high concurrency could exhaust threadpool │                                                                                  │
│ ├─────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤                                                                                  │
│ │ Battle-tested by millions of apps                       │                                                      │                                                                                  │
│ ├─────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤                                                                                  │
│ │ FastAPI handles sync→async via threadpool automatically │                                                      │                                                                                  │
│ └─────────────────────────────────────────────────────────┴──────────────────────────────────────────────────────┘                                                                                  │
│                                                                                                                                                                                                     │
│ Option B: asyncio.to_thread() wrapper or async HTTP client                                                                                                                                          │
│                                                                                                                                                                                                     │
│ ┌──────────────────────────────────┬────────────────────────────────────────────────┐                                                                                                               │
│ │               Pros               │                      Cons                      │                                                                                                               │
│ ├──────────────────────────────────┼────────────────────────────────────────────────┤                                                                                                               │
│ │ True non-blocking I/O            │ More code, more indirection                    │                                                                                                               │
│ ├──────────────────────────────────┼────────────────────────────────────────────────┤                                                                                                               │
│ │ Better under extreme concurrency │ Must reimplement Stripe SDK functionality      │                                                                                                               │
│ ├──────────────────────────────────┼────────────────────────────────────────────────┤                                                                                                               │
│ │                                  │ Stripe doesn't officially support async Python │                                                                                                               │
│ ├──────────────────────────────────┼────────────────────────────────────────────────┤                                                                                                               │
│ │                                  │ Harder to debug                                │                                                                                                               │
│ └──────────────────────────────────┴────────────────────────────────────────────────┘                                                                                                               │
│                                                                                                                                                                                                     │
│ Verdict: Option A. Stripe calls happen infrequently (checkout, webhook, seat update) — not on every request. The threadpool handles it fine. Premature async optimization adds complexity for no    │
│ real gain.                                                                                                                                                                                          │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ 6. Webhook Endpoint: Root Level vs Under /api/v1                                                                                                                                                    │
│                                                                                                                                                                                                     │
│ Option A: /webhooks/stripe at root ← RECOMMENDED                                                                                                                                                    │
│                                                                                                                                                                                                     │
│ ┌─────────────────────────────────────────────────────┬────────────────────────────────┐                                                                                                            │
│ │                        Pros                         │              Cons              │                                                                                                            │
│ ├─────────────────────────────────────────────────────┼────────────────────────────────┤                                                                                                            │
│ │ Consistent with existing /webhooks/sendgrid pattern │ Two router mount points in app │                                                                                                            │
│ ├─────────────────────────────────────────────────────┼────────────────────────────────┤                                                                                                            │
│ │ Clear that webhooks bypass JWT auth                 │                                │                                                                                                            │
│ ├─────────────────────────────────────────────────────┼────────────────────────────────┤                                                                                                            │
│ │ Easy to exclude from auth middleware                │                                │                                                                                                            │
│ └─────────────────────────────────────────────────────┴────────────────────────────────┘                                                                                                            │
│                                                                                                                                                                                                     │
│ Option B: /api/v1/webhooks/stripe                                                                                                                                                                   │
│                                                                                                                                                                                                     │
│ ┌─────────────────────────────┬────────────────────────────────────────────┐                                                                                                                        │
│ │            Pros             │                    Cons                    │                                                                                                                        │
│ ├─────────────────────────────┼────────────────────────────────────────────┤                                                                                                                        │
│ │ All routes under one prefix │ Must explicitly exclude from JWT auth      │                                                                                                                        │
│ ├─────────────────────────────┼────────────────────────────────────────────┤                                                                                                                        │
│ │ Cleaner router structure    │ Inconsistent with existing webhook pattern │                                                                                                                        │
│ └─────────────────────────────┴────────────────────────────────────────────┘                                                                                                                        │
│                                                                                                                                                                                                     │
│ Verdict: Option A. Follow existing pattern. The codebase already has /webhooks/sendgrid and /webhooks/gmail mounted at root.                                                                        │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ 7. Per-Seat Billing vs Flat Per-Plan                                                                                                                                                                │
│                                                                                                                                                                                                     │
│ Option A: Per-seat (plan × member count) ← YOUR CHOICE                                                                                                                                              │
│                                                                                                                                                                                                     │
│ ┌───────────────────────────────┬───────────────────────────────────────────────────┐                                                                                                               │
│ │             Pros              │                       Cons                        │                                                                                                               │
│ ├───────────────────────────────┼───────────────────────────────────────────────────┤                                                                                                               │
│ │ Revenue scales with team size │ More complex seat management (sync on add/remove) │                                                                                                               │
│ ├───────────────────────────────┼───────────────────────────────────────────────────┤                                                                                                               │
│ │ Standard SaaS pricing model   │ Must handle proration                             │                                                                                                               │
│ ├───────────────────────────────┼───────────────────────────────────────────────────┤                                                                                                               │
│ │ Fair — bigger teams pay more  │ Stripe quantity updates on every member change    │                                                                                                               │
│ └───────────────────────────────┴───────────────────────────────────────────────────┘                                                                                                               │
│                                                                                                                                                                                                     │
│ Option B: Flat per-plan                                                                                                                                                                             │
│                                                                                                                                                                                                     │
│ ┌────────────────────────────┬────────────────────────────────────────┐                                                                                                                             │
│ │            Pros            │                  Cons                  │                                                                                                                             │
│ ├────────────────────────────┼────────────────────────────────────────┤                                                                                                                             │
│ │ Simple — no seat counting  │ Large teams pay same as solo users     │                                                                                                                             │
│ ├────────────────────────────┼────────────────────────────────────────┤                                                                                                                             │
│ │ No sync needed with Stripe │ Revenue doesn't scale with usage       │                                                                                                                             │
│ ├────────────────────────────┼────────────────────────────────────────┤                                                                                                                             │
│ │ No proration headaches     │ Teams may abuse by adding many members │                                                                                                                             │
│ └────────────────────────────┴────────────────────────────────────────┘                                                                                                                             │
│                                                                                                                                                                                                     │
│ Verdict: Option A (per your requirement). Stripe handles proration automatically via create_prorations behavior.                                                                                    │
│                                                                                                                                                                                                     │
│ ---                                                                                                                                                                                                 │
│ Recommended Implementation Plan                                                                                                                                                                     │
│                                                                                                                                                                                                     │
│ New Files (15)                                                                                                                                                                                      │
│                                                                                                                                                                                                     │
│ ┌──────────────────────────────────────────────────────┬────────────────────────────────────────────────────────────┐                                                                               │
│ │                         File                         │                          Purpose                           │                                                                               │
│ ├──────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                               │
│ │ app/model/subscription_model.py                      │ Subscription table (sub_ prefix, 1:1 with org)             │                                                                               │
│ ├──────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                               │
│ │ app/model/billing_event_model.py                     │ Audit log of Stripe webhook events (be_ prefix)            │                                                                               │
│ ├──────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                               │
│ │ app/common/billing/__init__.py                       │ Package init                                               │                                                                               │
│ ├──────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                               │
│ │ app/common/billing/plan_limits.py                    │ Frozen dataclass with per-plan limits                      │                                                                               │
│ ├──────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                               │
│ │ app/common/billing/stripe_client.py                  │ Thin wrapper around Stripe SDK                             │                                                                               │
│ ├──────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                               │
│ │ app/common/billing/plan_enforcement.py               │ PlanEnforcer — resource count checks                       │                                                                               │
│ ├──────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                               │
│ │ app/db/repository/subscription_repository.py         │ Subscription CRUD                                          │                                                                               │
│ ├──────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                               │
│ │ app/db/repository/billing_event_repository.py        │ BillingEvent CRUD + idempotency check                      │                                                                               │
│ ├──────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                               │
│ │ app/service/billing_service.py                       │ Core: checkout, portal, webhooks, seat sync                │                                                                               │
│ ├──────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                               │
│ │ app/api/v1/controller/billing_api.py                 │ GET /billing, POST /billing/checkout, POST /billing/portal │                                                                               │
│ ├──────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                               │
│ │ app/api/v1/controller/billing_webhook_api.py         │ POST /webhooks/stripe (no JWT auth)                        │                                                                               │
│ ├──────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                               │
│ │ app/api/v1/request/billing_request.py                │ CheckoutRequest, PortalRequest                             │                                                                               │
│ ├──────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                               │
│ │ app/api/v1/response/billing_response.py              │ BillingInfoResponse, CheckoutResponse, PortalResponse      │                                                                               │
│ ├──────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                               │
│ │ alembic/versions/20260508_0005_add_billing_tables.py │ Creates subscription + billing_event tables                │                                                                               │
│ ├──────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤                                                                               │
│ │ scripts/backfill_stripe_customers.py                 │ One-time: create Stripe customers for existing orgs        │                                                                               │
│ └──────────────────────────────────────────────────────┴────────────────────────────────────────────────────────────┘                                                                               │
│                                                                                                                                                                                                     │
│ Modified Files (15)                                                                                                                                                                                 │
│                                                                                                                                                                                                     │
│ ┌──────────────────────────────────────────┬───────────────────────────────────────────────┐                                                                                                        │
│ │                   File                   │                    Change                     │                                                                                                        │
│ ├──────────────────────────────────────────┼───────────────────────────────────────────────┤                                                                                                        │
│ │ pyproject.toml                           │ Add stripe dependency                         │                                                                                                        │
│ ├──────────────────────────────────────────┼───────────────────────────────────────────────┤                                                                                                        │
│ │ app/settings.py                          │ Add 5 Stripe config fields                    │                                                                                                        │
│ ├──────────────────────────────────────────┼───────────────────────────────────────────────┤                                                                                                        │
│ │ app/common/enum/org.py                   │ Add SubscriptionStatus enum                   │                                                                                                        │
│ ├──────────────────────────────────────────┼───────────────────────────────────────────────┤                                                                                                        │
│ │ app/common/exceptions.py                 │ Add PlanLimitExceededError (HTTP 402)         │                                                                                                        │
│ ├──────────────────────────────────────────┼───────────────────────────────────────────────┤                                                                                                        │
│ │ app/api/tags.py                          │ Add Billing tag                               │                                                                                                        │
│ ├──────────────────────────────────────────┼───────────────────────────────────────────────┤                                                                                                        │
│ │ app/api/v1/router.py                     │ Register billing_router                       │                                                                                                        │
│ ├──────────────────────────────────────────┼───────────────────────────────────────────────┤                                                                                                        │
│ │ app/main.py                              │ Mount webhook router at root                  │                                                                                                        │
│ ├──────────────────────────────────────────┼───────────────────────────────────────────────┤                                                                                                        │
│ │ app/service/user_service.py              │ Call ensure_stripe_customer in auto-provision │                                                                                                        │
│ ├──────────────────────────────────────────┼───────────────────────────────────────────────┤                                                                                                        │
│ │ app/service/organization_service.py      │ Call ensure_stripe_customer on org creation   │                                                                                                        │
│ ├──────────────────────────────────────────┼───────────────────────────────────────────────┤                                                                                                        │
│ │ app/service/org_membership_service.py    │ Plan limit check + seat sync on invite/remove │                                                                                                        │
│ ├──────────────────────────────────────────┼───────────────────────────────────────────────┤                                                                                                        │
│ │ app/service/mailbox_service.py           │ Plan limit check before connecting mailbox    │                                                                                                        │
│ ├──────────────────────────────────────────┼───────────────────────────────────────────────┤                                                                                                        │
│ │ app/service/campaign_service.py          │ Plan limit check before creating campaign     │                                                                                                        │
│ ├──────────────────────────────────────────┼───────────────────────────────────────────────┤                                                                                                        │
│ │ app/service/developer_profile_service.py │ Plan limit check before creating profile      │                                                                                                        │
│ ├──────────────────────────────────────────┼───────────────────────────────────────────────┤                                                                                                        │
│ │ alembic/env.py                           │ Import Subscription, BillingEvent models      │                                                                                                        │
│ ├──────────────────────────────────────────┼───────────────────────────────────────────────┤                                                                                                        │
│ │ tests/conftest.py                        │ Import new models, add mock_stripe fixture    │                                                                                                        │
│ └──────────────────────────────────────────┴───────────────────────────────────────────────┘                                                                                                        │
│                                                                                                                                                                                                     │
│ Implementation Order                                                                                                                                                                                │
│                                                                                                                                                                                                     │
│ Batch 1 — Foundation (no business logic changes):                                                                                                                                                   │
│ 1. pyproject.toml — add stripe dependency                                                                                                                                                           │
│ 2. app/settings.py — add Stripe config fields                                                                                                                                                       │
│ 3. app/common/enum/org.py — add SubscriptionStatus                                                                                                                                                  │
│ 4. New models: subscription_model.py, billing_event_model.py                                                                                                                                        │
│ 5. Alembic migration 0005                                                                                                                                                                           │
│ 6. Register models in alembic/env.py + tests/conftest.py                                                                                                                                            │
│                                                                                                                                                                                                     │
│ Batch 2 — Stripe Integration (no API changes yet):                                                                                                                                                  │
│ 7. app/common/billing/stripe_client.py — Stripe SDK wrapper                                                                                                                                         │
│ 8. Repositories: subscription_repository.py, billing_event_repository.py                                                                                                                            │
│ 9. app/service/billing_service.py — core billing service                                                                                                                                            │
│ 10. app/common/billing/plan_limits.py + plan_enforcement.py                                                                                                                                         │
│ 11. app/common/exceptions.py — add PlanLimitExceededError                                                                                                                                           │
│                                                                                                                                                                                                     │
│ Batch 3 — API Layer:                                                                                                                                                                                │
│ 12. Request/response schemas + tags                                                                                                                                                                 │
│ 13. Controllers: billing_api.py, billing_webhook_api.py                                                                                                                                             │
│ 14. Wire up routes in router.py + main.py                                                                                                                                                           │
│                                                                                                                                                                                                     │
│ Batch 4 — Integration (the delicate part):                                                                                                                                                          │
│ 15. user_service.py — Stripe customer on auto-provision                                                                                                                                             │
│ 16. organization_service.py — Stripe customer on org creation                                                                                                                                       │
│ 17. org_membership_service.py — limit checks + seat sync                                                                                                                                            │
│ 18. Resource services (mailbox, campaign, profile) — limit checks                                                                                                                                   │
│                                                                                                                                                                                                     │
│ Batch 5 — Testing:                                                                                                                                                                                  │
│ 19. Test files: test_plan_limits.py, test_billing_service.py, test_billing_api.py, test_billing_webhook.py                                                                                          │
│ 20. scripts/backfill_stripe_customers.py                                                                                                                                                            │
│                                                                                                                                                                                                     │
│ Plan Limits (Default Values)                                                                                                                                                                        │
│                                                                                                                                                                                                     │
│ ┌────────────────────────┬──────┬───────┬────────────┐                                                                                                                                              │
│ │        Resource        │ Free │  Pro  │ Enterprise │                                                                                                                                              │
│ ├────────────────────────┼──────┼───────┼────────────┤                                                                                                                                              │
│ │ Emails/month           │ 200  │ 5,000 │ 100,000    │                                                                                                                                              │
│ ├────────────────────────┼──────┼───────┼────────────┤                                                                                                                                              │
│ │ Mailboxes              │ 1    │ 5     │ 50         │                                                                                                                                              │
│ ├────────────────────────┼──────┼───────┼────────────┤                                                                                                                                              │
│ │ Campaigns              │ 2    │ 20    │ 200        │                                                                                                                                              │
│ ├────────────────────────┼──────┼───────┼────────────┤                                                                                                                                              │
│ │ Developer Profiles     │ 100  │ 5,000 │ 100,000    │                                                                                                                                              │
│ ├────────────────────────┼──────┼───────┼────────────┤                                                                                                                                              │
│ │ Ingestion Jobs/month   │ 5    │ 50    │ 500        │                                                                                                                                              │
│ ├────────────────────────┼──────┼───────┼────────────┤                                                                                                                                              │
│ │ Enrichment Calls/month │ 50   │ 2,000 │ 50,000     │                                                                                                                                              │
│ ├────────────────────────┼──────┼───────┼────────────┤                                                                                                                                              │
│ │ Projects               │ 1    │ 10    │ 100        │                                                                                                                                              │
│ ├────────────────────────┼──────┼───────┼────────────┤                                                                                                                                              │
│ │ Org Members            │ 1    │ 10    │ 100        │                                                                                                                                              │
│ └────────────────────────┴──────┴───────┴────────────┘                                                                                                                                              │
│                                                                                                                                                                                                     │
│ API Endpoints                                                                                                                                                                                       │
│                                                                                                                                                                                                     │
│ ┌────────┬──────────────────────────┬─────────────────────────┬───────────────────────────────────────────────┐                                                                                     │
│ │ Method │           Path           │          Auth           │                  Description                  │                                                                                     │
│ ├────────┼──────────────────────────┼─────────────────────────┼───────────────────────────────────────────────┤                                                                                     │
│ │ GET    │ /api/v1/billing          │ Owner/Admin             │ Current plan, limits, seat count, period info │                                                                                     │
│ ├────────┼──────────────────────────┼─────────────────────────┼───────────────────────────────────────────────┤                                                                                     │
│ │ POST   │ /api/v1/billing/checkout │ Owner/Admin             │ Create Stripe Checkout session → returns URL  │                                                                                     │
│ ├────────┼──────────────────────────┼─────────────────────────┼───────────────────────────────────────────────┤                                                                                     │
│ │ POST   │ /api/v1/billing/portal   │ Owner/Admin             │ Create Stripe Customer Portal → returns URL   │                                                                                     │
│ ├────────┼──────────────────────────┼─────────────────────────┼───────────────────────────────────────────────┤                                                                                     │
│ │ POST   │ /webhooks/stripe         │ None (Stripe signature) │ Process webhook events                        │                                                                                     │
│ └────────┴──────────────────────────┴─────────────────────────┴───────────────────────────────────────────────┘                                                                                     │
│                                                                                                                                                                                                     │
│ Key Flows                                                                                                                                                                                           │
│                                                                                                                                                                                                     │
│ Upgrade: Frontend calls POST /billing/checkout → user redirected to Stripe Checkout → pays → Stripe sends checkout.session.completed webhook → we link subscription → Stripe sends                  │
│ customer.subscription.updated → we sync plan to org.                                                                                                                                                │
│                                                                                                                                                                                                     │
│ Seat change: Member added/removed → org_membership_service calls billing_service.sync_seat_count() → Stripe subscription quantity updated → proration applied automatically.                        │
│                                                                                                                                                                                                     │
│ Limit enforcement: Service creates resource → PlanEnforcer.check_*() counts existing resources → if at limit, raises PlanLimitExceededError (HTTP 402) → frontend shows upgrade prompt.             │
│                                                                                                                                                                                                     │
│ Cancellation: User goes to Stripe Customer Portal → cancels → Stripe sends customer.subscription.deleted → we downgrade org to free plan.                                                           │
│                                                                                                                                                                                                     │
│ Verification                                                                                                                                                                                        │
│                                                                                                                                                                                                     │
│ 1. make lint + make test — all pass                                                                                                                                                                 │
│ 2. GET /api/v1/billing returns free plan info for auto-provisioned org                                                                                                                              │
│ 3. POST /api/v1/billing/checkout returns a Stripe Checkout URL                                                                                                                                      │
│ 4. Creating resources beyond plan limit returns HTTP 402                                                                                                                                            │
│ 5. Adding a member syncs seat count with Stripe                                                                                                                                                     │
│ 6. Stripe webhook events update local subscription state                                                                                                                                            │
│ 7. POST /webhooks/stripe with invalid signature returns 400                                                                                                                                         │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯


⏺ Here's the testing strategy, broken into layers:          
                                                                                                                                                                                                       
  1. Already passing (no Stripe needed)                                                    
                                                                                                                                                                                                       
  make test   # 174 tests pass right now                                                                                                                                                               
                                                                                                                                                                                                       
  This covers:                                                                                                                                                                                         
  - Plan limits — frozen dataclass values, unknown plan defaults, immutability                                                                                                                         
  - BillingService unit tests — ensure_stripe_customer (mocked), idempotency, get_billing_info, sync_seat_count                                                                                        
  - Webhook endpoint — invalid signature → 400, valid event → 200 (all mocked)                                                                                                                         
  - Billing API — GET /billing returns free plan for auto-provisioned org

  2. Manual E2E testing with Stripe test keys

  To test the full Stripe flow, you need test credentials:

  # Add to .env.local
  STRIPE_SECRET_KEY=sk_test_...           # from Stripe Dashboard → Developers → API keys
  STRIPE_WEBHOOK_SECRET=whsec_...         # from Stripe CLI (see below)
  STRIPE_PRICE_ID_PRO=price_...           # create a test product+price in Stripe Dashboard
  STRIPE_PRICE_ID_ENTERPRISE=price_...    # same, for enterprise tier

  Step-by-step test flow:

  A. Verify billing info (free plan)
  curl -H "Authorization: Bearer <jwt>" http://localhost:8000/api/v1/billing
  # Should return: plan=free, seat_count=1, status=active

  B. Create a checkout session
  curl -X POST http://localhost:8000/api/v1/billing/checkout \
    -H "Authorization: Bearer <jwt>" \
    -H "Content-Type: application/json" \
    -d '{"plan":"pro","success_url":"http://localhost:3000/success","cancel_url":"http://localhost:3000/cancel"}'
  # Returns: { "result": { "checkout_url": "https://checkout.stripe.com/..." } }
  # Open the URL → use Stripe test card 4242424242424242

  C. Test webhooks locally with Stripe CLI
  # Install: brew install stripe/stripe-cli/stripe
  stripe login
  stripe listen --forward-to localhost:8000/webhooks/stripe
  # Copy the webhook signing secret (whsec_...) → put in STRIPE_WEBHOOK_SECRET
  # Now complete a checkout — webhook events will forward to your local server

  D. Verify plan upgraded after checkout
  curl -H "Authorization: Bearer <jwt>" http://localhost:8000/api/v1/billing
  # Should now show: plan=pro, stripe_subscription_id=sub_...

  E. Test plan enforcement
  # On free plan with 1 mailbox limit:
  # Connect 1 mailbox → 201
  # Connect 2nd mailbox → 402 (Plan limit reached)

  F. Test seat sync
  # Invite a member → check Stripe Dashboard, subscription quantity should update
  curl -X POST http://localhost:8000/api/v1/organization/{org_id}/members/invite \
    -H "Authorization: Bearer <jwt>" \
    -H "Content-Type: application/json" \
    -d '{"email":"teammate@example.com","role":"member"}'

  G. Customer portal
  curl -X POST http://localhost:8000/api/v1/billing/portal \
    -H "Authorization: Bearer <jwt>" \
    -H "Content-Type: application/json" \
    -d '{"return_url":"http://localhost:3000/billing"}'
  # Open the portal URL → cancel subscription → webhook fires → org downgrades to free

  3. Stripe test cards

  ┌─────────────────────┬─────────────────────────────────┐
  │        Card         │             Result              │
  ├─────────────────────┼─────────────────────────────────┤
  │ 4242 4242 4242 4242 │ Success                         │
  ├─────────────────────┼─────────────────────────────────┤
  │ 4000 0000 0000 3220 │ Requires 3DS authentication     │
  ├─────────────────────┼─────────────────────────────────┤
  │ 4000 0000 0000 0341 │ Payment fails (attach succeeds) │
  ├─────────────────────┼─────────────────────────────────┤
  │ 4000 0000 0000 9995 │ Insufficient funds              │
  └─────────────────────┴─────────────────────────────────┘

  Any future date + any 3-digit CVC works for test cards.