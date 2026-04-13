# Crowdsourced Org Graph System -- ER Diagram & DB Schema Design

## ER Diagram

```
┌─────────────────────────────┐
│         organization        │
├─────────────────────────────┤
│ PK  id          (String)    │──── "org_<uuid>"
│     name        (String)    │
│     domain      (String) UQ │
│     industry    (String)    │
│     logo_url    (String)    │
│     metadata    (JSON)      │
│     is_deleted  (Boolean)   │
│     created_by  (String)    │
│     updated_by  (String)    │
│     created_at  (Timestamp) │
│     updated_at  (Timestamp) │
└──────────┬──────────────────┘
           │
           │ 1
           │
           │            ┌─────────────────────────────┐
           │            │          employee            │
           │            ├─────────────────────────────┤
           │            │ PK  id          (String)    │──── "emp_<uuid>"
           │            │     canonical_name (String)  │
           │            │     primary_email (String) UQ│
           │            │     profile_data  (JSON)    │
           │            │     is_deleted    (Boolean)  │
           │            │     created_by    (String)   │
           │            │     updated_by    (String)   │
           │            │     created_at    (Timestamp)│
           │            │     updated_at    (Timestamp)│
           │            └──────┬──────────────────────┘
           │                   │
           │ *                 │ *
           ▼                   ▼
┌──────────────────────────────────────────────┐
│                 employment                    │
├──────────────────────────────────────────────┤
│ PK  id              (String)                 │──── "empl_<uuid>"
│ FK  employee_id     (String) → employee.id   │
│ FK  org_id          (String) → organization.id│
│     title           (String)                  │
│     department      (String)                  │
│     level           (String)                  │
│     location        (String)                  │
│     valid_from      (Timestamp)               │
│     valid_to        (Timestamp)               │
│     is_current      (Boolean)                 │
│     is_deleted      (Boolean)                 │
│     created_by      (String)                  │
│     updated_by      (String)                  │
│     created_at      (Timestamp)               │
│     updated_at      (Timestamp)               │
│ IDX (employee_id, org_id)                     │
└──────────────────────────────────────────────┘
           │
           │ 1
           │
           ▼
┌──────────────────────────────────────────────┐
│            reporting_relationship             │
├──────────────────────────────────────────────┤
│ PK  id                  (String)             │──── "rr_<uuid>"
│ FK  org_id              (String) → organization.id│
│ FK  employee_id         (String) → employee.id│
│ FK  manager_employee_id (String) → employee.id│
│     relationship_type   (Enum)                │──── solid_line | dotted_line | matrix
│     status              (Enum)                │──── confirmed | probable | weak
│     confidence_score    (Numeric 5,4)         │
│     valid_from          (Timestamp)           │
│     valid_to            (Timestamp)           │
│     is_current          (Boolean)             │
│     is_deleted          (Boolean)             │
│     created_by          (String)              │
│     updated_by          (String)              │
│     created_at          (Timestamp)           │
│     updated_at          (Timestamp)           │
│ IDX (org_id, employee_id)                     │
│ IDX (manager_employee_id)                     │
└──────────────────────────────────────────────┘


┌──────────────────────────────────────────────┐
│              career_event                     │
├──────────────────────────────────────────────┤
│ PK  id              (String)                 │──── "ce_<uuid>"
│ FK  employee_id     (String) → employee.id   │
│ FK  org_id          (String) → organization.id│
│ FK  employment_id   (String) → employment.id │
│     event_type      (Enum)                    │──── join | leave | promotion | transfer
│     effective_at    (Timestamp)               │     | title_change | manager_change
│     recorded_at     (Timestamp)               │     | role_change
│     payload         (JSON)                    │
│ IDX (employee_id)                             │
└──────────────────────────────────────────────┘


┌──────────────────────────────────────────────┐
│              reporting_claim                  │
├──────────────────────────────────────────────┤
│ PK  id              (String)                 │──── "claim_<uuid>"
│ FK  org_id          (String) → organization.id│
│ FK  employee_id     (String) → employee.id   │
│ FK  manager_id      (String) → employee.id   │
│     claimant_id     (String)                  │──── actor who submitted
│     state           (Enum)                    │──── draft | submitted | validation
│     confidence_score (Numeric 5,4)            │     | pending_counterparty
│     submitted_at    (Timestamp)               │     | pending_moderation | verified
│     resolved_at     (Timestamp)               │     | rejected | expired | disputed
│     expires_at      (Timestamp)               │     | superseded
│ FK  superseded_by   (String) → reporting_claim.id│
│     is_deleted      (Boolean)                 │
│     created_by      (String)                  │
│     updated_by      (String)                  │
│     created_at      (Timestamp)               │
│     updated_at      (Timestamp)               │
│ IDX (employee_id, manager_id)                 │
│ IDX (state)                                   │
│ IDX (claimant_id)                             │
└──────────────┬───────────────────────────────┘
               │
               │ 1
               │
               ▼ *
┌──────────────────────────────────────────────┐
│              claim_evidence                   │
├──────────────────────────────────────────────┤
│ PK  id              (String)                 │──── "evi_<uuid>"
│ FK  claim_id        (String) → reporting_claim.id│
│     actor_id        (String)                  │
│     evidence_type   (Enum)                    │──── self_claim | manager_confirmation
│     response        (Enum)                    │     | peer_confirmation | system
│     weight          (Numeric 5,4)             │     | rejection
│     comment         (String)                  │
│     created_at      (Timestamp)               │──── response: confirm | reject | abstain
└──────────────────────────────────────────────┘


┌──────────────────────────────────────────────┐
│            contributor_score                  │
├──────────────────────────────────────────────┤
│ PK  id                       (String)        │──── "cs_<uuid>"
│     actor_id                 (String) UQ     │
│     total_claims_submitted   (Integer)       │
│     total_claims_verified    (Integer)       │
│     total_confirmations_given (Integer)      │
│     total_rejections_given   (Integer)       │
│     visibility_level         (Integer)       │──── 0-3
│     raw_score                (Numeric 10,2)  │
│     created_at               (Timestamp)     │
│     updated_at               (Timestamp)     │
└──────────────────────────────────────────────┘


┌──────────────────────────────────────────────┐
│              event_log                        │
├──────────────────────────────────────────────┤
│ PK  id              (String)                 │──── "evt_<uuid>"
│     sequence_no     (Integer)                │──── monotonically increasing
│     entity_type     (String)                 │──── org | employee | employment | ...
│     entity_id       (String)                 │
│     action          (String)                 │──── create | update | delete | ...
│     before_state    (JSON)                   │
│     after_state     (JSON)                   │
│     actor_id        (String)                 │
│     timestamp       (Timestamp)              │
│     prev_hash       (Text)                   │──── SHA-256 hash chain
│     event_hash      (Text)                   │
│ IDX (entity_type, entity_id)                 │
│ IDX (sequence_no)                            │
│ IDX (actor_id)                               │
└──────────────────────────────────────────────┘
```

---

## Relationship Summary

```
organization  1 ──── * employment       (org has many employments)
employee      1 ──── * employment       (employee has many employments)
employment    1 ──── * career_event     (employment has many career events)

organization  1 ──── * reporting_relationship  (org scopes relationships)
employee      1 ──── * reporting_relationship  (as report, via employee_id)
employee      1 ──── * reporting_relationship  (as manager, via manager_employee_id)

organization  1 ──── * reporting_claim         (claim scoped to org)
employee      1 ──── * reporting_claim         (as report, via employee_id)
employee      1 ──── * reporting_claim         (as manager, via manager_id)

reporting_claim 1 ── * claim_evidence          (claim has many evidence items)
reporting_claim 1 ── 0..1 reporting_claim       (self-FK: superseded_by)
```

---

## Enum Definitions

| Enum | Values |
|------|--------|
| **RelationshipType** | `solid_line`, `dotted_line`, `matrix` |
| **RelationshipStatus** | `confirmed`, `probable`, `weak` |
| **CareerEventType** | `join`, `leave`, `promotion`, `transfer`, `title_change`, `manager_change`, `role_change` |
| **ClaimState** | `draft`, `submitted`, `validation`, `pending_counterparty`, `pending_moderation`, `verified`, `rejected`, `expired`, `disputed`, `superseded` |
| **EvidenceType** | `self_claim`, `manager_confirmation`, `peer_confirmation`, `system`, `rejection` |
| **EvidenceResponse** | `confirm`, `reject`, `abstain` |
| **EntityType** | `org`, `employee`, `employment`, `reporting_relationship`, `career_event`, `reporting_claim` |
| **VisibilityLevel** | `0` (none), `1` (basic), `2` (extended), `3` (full) |

---

## Key Design Decisions (aligned with context0-python-backend patterns)

### 1. Primary Keys
- **Prefixed string UUIDs**: `org_<uuid>`, `emp_<uuid>`, `empl_<uuid>`, etc.
- Matches context0 pattern: `user_<uuid>`, `org_<uuid>`, `cred_<uuid>`
- Human-readable in logs, URLs, and debugging

### 2. Soft Delete
- All main entities have `is_deleted = Column(Boolean, default=False)`
- Matches context0 pattern used on `User`, `Organization`, `Credential`
- Allows audit trail and recovery

### 3. Audit Columns
- `created_by` / `updated_by` on all main entities (String, actor_id)
- Matches context0's `created_by` / `updated_by` on `Credential`

### 4. Timestamps
- `TIMESTAMP(timezone=True)` for all datetime columns
- Matches context0 pattern on `User`, `Organization`

### 5. Table Naming
- Singular, lowercase: `organization`, `employee`, `employment`
- Matches context0: `user`, `organization`, `credential`

### 6. JSON Columns
- `JSON().with_variant(JSONB, "postgresql")` for cross-database compat
- SQLite uses plain JSON, PostgreSQL uses JSONB for indexing

### 7. Enums
- All enums use `(str, Enum)` pattern for JSON serializability
- Matches context0: `UserRole(str, Enum)`, `MemoryType(str, Enum)`

### 8. Event Sourcing (event_log)
- Append-only table with SHA-256 hash chaining
- Similar to context0's `audit_log` pattern but with hash integrity
- Captures `before_state` / `after_state` snapshots (like context0's `AuditLogEntry`)

---

## State Machine: Claim Lifecycle

```
                    ┌──────────┐
                    │  DRAFT   │
                    └────┬─────┘
                         │ submit
                         ▼
                    ┌──────────┐
                    │SUBMITTED │
                    └────┬─────┘
                         │ validate
                         ▼
                    ┌──────────┐
              ┌─────│VALIDATION│─────┐
              │     └──────────┘     │
              │ request_             │ request_
              │ counterparty         │ moderation
              ▼                      ▼
     ┌────────────────┐    ┌─────────────────┐
     │PENDING_        │    │PENDING_         │
     │COUNTERPARTY    │    │MODERATION       │
     └──┬──┬──┬──┬────┘    └──┬──┬───────────┘
        │  │  │  │            │  │
        │  │  │  │ dispute    │  │
        │  │  │  └───►┌───────┘  │
        │  │  │       │          │
        │  │  │  ┌────┴────┐     │
        │  │  │  │DISPUTED │─────┘
        │  │  │  └─────────┘ moderate
        │  │  │
        │  │  │ expire
        │  │  └───►┌─────────┐
        │  │       │ EXPIRED │
        │  │       └─────────┘
        │  │
        │  │ reject
        │  └──────►┌──────────┐
        │          │ REJECTED │◄─── (from PENDING_MODERATION too)
        │          └──────────┘
        │ confirm
        └─────────►┌──────────┐
                   │ VERIFIED │◄─── (from PENDING_MODERATION: approve)
                   └──────────┘

    ANY state + "supersede" ──► SUPERSEDED
```

---

## Confidence Scoring (Deterministic)

| Evidence Type | Weight |
|---|---|
| self_claim | +0.45 |
| manager_confirmation | +0.40 |
| peer_confirmation | +0.10 |
| system | +0.80 |
| rejection | -0.80 |

`confidence = clamp(sum(weights), 0.0, 1.0)`

| Score Range | Status |
|---|---|
| >= 0.90 | confirmed |
| >= 0.65 | probable |
| < 0.65 | weak |

---

## Visibility Levels (Progressive Disclosure)

| Level | Score Required | Access |
|---|---|---|
| 0 (None) | < 1 | Only own direct edges, names blurred |
| 1 (Basic) | >= 1 | 2-hop BFS from self, unverified visible |
| 2 (Extended) | >= 5 | 5-hop BFS from self, names visible |
| 3 (Full) | >= 10 | Full org graph |

Contributor score: `(submitted * 1) + (verified * 3) + (confirmations * 2) - (rejections * 0.5)`
