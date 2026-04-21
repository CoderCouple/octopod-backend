# Octopod Backend

A crowdsourced, time-aware organizational graph system built with FastAPI. Octopod models employees, organizations, and reporting relationships over time using crowdsourced claims with a state-machine-driven verification workflow, confidence scoring for trust, event sourcing for auditability, and progressive visibility (Glassdoor-style) for incentives.

## Architecture

The application follows a clean layered architecture:

```
Controller (API) -> Service (Business Logic) -> Repository (Data Access) -> Model (ORM)
     |                                                                         |
  Request DTO                                                             SQLAlchemy
  Response DTO                                                            Models
```

**Key design decisions:**
- **Controller layer** handles HTTP concerns, dependency injection, and response wrapping
- **Service layer** contains all business logic, validation, and event logging
- **Repository layer** provides data access abstraction with flush-not-commit semantics
- **Model layer** defines SQLAlchemy ORM models with prefixed UUIDs (e.g. `org_`, `emp_`, `claim_`)
- **Request/Response DTOs** separate API contracts from internal models

## Project Structure

```
octopod-backend/
├── app/
│   ├── main.py                          # FastAPI app initialization and lifespan
│   ├── settings.py                      # Environment-based config (pydantic-settings)
│   ├── api/
│   │   ├── router.py                    # Root API router
│   │   ├── tags.py                      # OpenAPI tag definitions
│   │   └── v1/
│   │       ├── router.py               # V1 router aggregating all controllers
│   │       ├── controller/
│   │       │   ├── health_api.py        # GET /health, GET /ready
│   │       │   ├── org_api.py           # Organization CRUD
│   │       │   ├── employee_api.py      # Employee CRUD + employment lookups
│   │       │   ├── employment_api.py    # Employment CRUD + end employment
│   │       │   ├── relationship_api.py  # Reporting relationships (read-only)
│   │       │   ├── claim_api.py         # Claim lifecycle (submit/confirm/reject)
│   │       │   ├── graph_api.py         # Org graph + cycle detection
│   │       │   └── timeline_api.py      # Career timeline + reporting history
│   │       ├── request/                 # Pydantic request schemas
│   │       └── response/               # Pydantic response schemas
│   ├── common/
│   │   ├── auth/auth.py                 # Actor ID extraction from headers
│   │   ├── enum/                        # Enums (claim states, relationship types, etc.)
│   │   ├── exceptions.py               # Custom HTTP exceptions
│   │   ├── hashing.py                   # SHA-256 event hash computation
│   │   └── pagination.py               # Generic pagination params/response
│   ├── db/
│   │   ├── base.py                      # SQLAlchemy DeclarativeBase
│   │   ├── engine.py                    # Async/sync engine factories (cached)
│   │   ├── session.py                   # get_db() async session dependency
│   │   └── repository/                  # Data access repositories
│   ├── model/                           # SQLAlchemy ORM models (9 tables)
│   ├── service/                         # Business logic services
│   │   ├── org_service.py               # Organization CRUD with event logging
│   │   ├── employee_service.py          # Employee CRUD with event logging
│   │   ├── employment_service.py        # Employment lifecycle + career events
│   │   ├── event_log_service.py         # Append-only event log with hash chaining
│   │   ├── claim_service.py             # Full claim lifecycle orchestration
│   │   ├── state_machine.py             # Claim state transition table
│   │   ├── resolution_engine.py         # Confidence scoring (Decimal arithmetic)
│   │   ├── graph_service.py             # Org graph + DFS cycle detection
│   │   ├── timeline_service.py          # Career timeline queries
│   │   ├── contributor_service.py       # Contributor scoring + visibility levels
│   │   └── visibility_service.py        # BFS-based graph visibility filtering
│   └── middleware/
│       └── actor_context.py             # Actor context middleware
├── tests/                               # pytest test suite (59 tests)
├── sql/
│   └── schema.sql                       # PostgreSQL schema + seed data
├── alembic/                             # Database migration scripts
├── docker-compose.yml                   # Docker services (app, postgres, pgadmin)
├── Dockerfile                           # Python 3.11 + Poetry container
├── Makefile                             # Development commands
└── pyproject.toml                       # Poetry dependencies + tool configs
```

## Prerequisites

- **Python** >= 3.11
- **Poetry** >= 1.8
- **Docker** and **Docker Compose** (for containerized setup)

## Quick Start (Docker)

The fastest way to get everything running:

```bash
# 1. Clone and enter the project
cd octopod-backend

# 2. Copy the environment file
cp .env.example .env

# 3. Start all services (app + postgres + pgadmin)
make docker-up

# 4. Verify it's running
curl http://localhost:8000/api/v1/health
```

This starts three containers:

| Service | URL | Description |
|---------|-----|-------------|
| **web** | http://localhost:8000 | FastAPI application |
| **db** | localhost:5432 | PostgreSQL 16 |
| **pgadmin** | http://localhost:8080 | pgAdmin (admin@octopod.dev / octopod) |

The database schema and seed data are automatically loaded from `sql/schema.sql` on first startup.

### Docker Commands

```bash
make docker-up       # Start all containers
make docker-down     # Stop all containers
make docker-build    # Rebuild containers
make docker-logs     # Tail container logs
make docker-db       # Open psql shell in the database container
```

## Local Development (without Docker)

```bash
# 1. Install dependencies
poetry install

# 2. Set up the environment
cp .env.example .env
# Edit .env: set POSTGRES_HOST=localhost and configure your local PostgreSQL

# 3. Apply the database schema
psql -U octopod -d octopod_db -f sql/schema.sql

# 4. Run the dev server with hot reload
make dev
```

The server starts at http://localhost:8000. Swagger docs are at http://localhost:8000/docs.

### Running from PyCharm

1. Create a new **Python** run configuration
2. Set **Script path** to the project's `octopod_app.py`
3. Set **Working directory** to the project root
4. Run it

## Development Commands

```bash
make dev              # Run dev server with hot reload
make run              # Run production server
make test             # Run pytest test suite
make lint             # Run ruff linter
make format           # Format code (black + isort + ruff)
make pre-commit       # Install pre-commit hooks
make pre-commit-run   # Run pre-commit on all files
make migrate          # Apply Alembic database migrations
```

## Running Tests

Tests use an in-memory SQLite database and require no external services:

```bash
make test
# or
poetry run pytest -v
```

The test suite includes 59 tests covering:
- **API tests** -- health, org, employee, employment, claim, graph, timeline endpoints
- **Service tests** -- event log, state machine, resolution engine, contributor scoring, visibility filtering

## API Endpoints

All endpoints are under `/api/v1`. Interactive Swagger docs at `/docs`.

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness probe -- returns `{"status": "healthy"}` |
| GET | `/ready` | Readiness probe -- checks database and cache dependencies |

### Organizations

| Method | Path | Description |
|--------|------|-------------|
| POST | `/org` | Create a new organization |
| GET | `/org` | List organizations (paginated) |
| GET | `/org/{org_id}` | Get organization by ID |
| PATCH | `/org/{org_id}` | Partial update (name, domain, industry, etc.) |
| DELETE | `/org/{org_id}` | Soft-delete organization |

### Employees

| Method | Path | Description |
|--------|------|-------------|
| POST | `/employee` | Create a new employee |
| GET | `/employee` | List employees (paginated) |
| GET | `/employee/{id}` | Get employee by ID |
| PATCH | `/employee/{id}` | Partial update (name, email, profile data) |
| GET | `/employee/{id}/employments` | List employee's employment history |

### Employments

| Method | Path | Description |
|--------|------|-------------|
| POST | `/employment` | Create employment (links employee to org, creates JOIN event) |
| GET | `/employment/{id}` | Get employment by ID |
| PATCH | `/employment/{id}` | Partial update (title, department, level, etc.) |
| POST | `/employment/{id}/end` | End employment (sets end date, creates LEAVE event) |

### Reporting Relationships (read-only)

Relationships are created via the claims workflow, not directly.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/relationship` | List relationships (filter by org, employee, manager, is_current) |
| GET | `/relationship/{id}` | Get relationship by ID |

### Claims (Crowdsourced Verification)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/claim` | Submit a reporting-relationship claim |
| GET | `/claim` | List claims (filter by org, employee, claimant, state) |
| GET | `/claim/pending` | Get claims pending your confirmation (uses X-Actor-Id header) |
| GET | `/claim/{id}` | Get claim details + allowed state-machine actions |
| POST | `/claim/{id}/confirm` | Confirm or reject a pending claim |

### Graph

| Method | Path | Description |
|--------|------|-------------|
| GET | `/graph/org/{org_id}` | Get the org reporting graph (nodes + edges), filtered by visibility |
| GET | `/graph/org/{org_id}/cycles` | Detect cycles in the reporting graph |

### Timeline

| Method | Path | Description |
|--------|------|-------------|
| GET | `/timeline/employee/{id}` | Career event timeline (join, leave, promotion, etc.) |
| GET | `/timeline/employee/{id}/reporting-history` | Reporting relationship change history |

## Core Concepts

### Claim Lifecycle

Claims go through a state machine workflow:

```
DRAFT -> SUBMITTED -> VALIDATION -> PENDING_COUNTERPARTY
                                         |
                              confirm -> VERIFIED (creates relationship)
                              reject  -> REJECTED
                              expire  -> EXPIRED (after 14 days)
                              dispute -> DISPUTED -> PENDING_MODERATION
                                                          |
                                               approve -> VERIFIED
                                               reject  -> REJECTED
```

Any state can transition to **SUPERSEDED** via the `supersede` action.

When a claim is **VERIFIED**, it automatically creates or updates the canonical reporting relationship in the `reporting_relationship` table.

### Event Sourcing

Every mutation (create, update, delete) appends an immutable event to the `event_log` table. Events are linked via SHA-256 hash chaining for tamper detection:

```
event_hash = SHA256(prev_hash + entity_type + entity_id + action + after_state + actor_id + timestamp)
```

The chain integrity can be verified via `EventLogService.verify_chain_integrity()`.

### Confidence Scoring

The resolution engine computes confidence scores for claims using weighted evidence:

| Evidence Type | Weight |
|--------------|--------|
| Self-claim | +0.45 |
| Manager confirmation | +0.40 |
| Peer confirmation | +0.10 |
| System verification | +0.80 |
| Rejection | -0.80 |

Scores are clamped to `[0.0, 1.0]` and determine relationship status:
- **>= 0.90**: `confirmed`
- **>= 0.65**: `probable`
- **< 0.65**: `weak`

### Visibility Levels (Progressive Disclosure)

Contributors earn visibility into the org graph by participating:

| Level | Required Score | Graph Access |
|-------|---------------|-------------|
| 0 (None) | < 1 | Only direct edges, names blurred |
| 1 (Basic) | >= 1 | 2-hop BFS from self, names blurred |
| 2 (Extended) | >= 5 | 5-hop BFS from self, names visible |
| 3 (Full) | >= 10 | Full graph access |

Scoring formula:
```
raw_score = (claims_submitted * 1) + (claims_verified * 3) + (confirmations * 2) - (rejections * 0.5)
```

### Cycle Detection

The graph service uses DFS-based cycle detection to prevent circular reporting chains. Before promoting a verified claim to a canonical relationship, the system checks `would_create_cycle()` and skips promotion if a cycle would result.

### Single Solid-Line Manager

Each employee can have at most one confirmed solid-line manager per organization. If a new claim conflicts with an existing solid-line relationship, the new relationship is automatically downgraded to `dotted_line`.

## Database

### Schema

The database schema is defined in `sql/schema.sql` and includes 9 tables:

| Table | PK Prefix | Description |
|-------|----------|-------------|
| `organization` | `org_` | Companies and organizations |
| `employee` | `emp_` | Individual employees |
| `employment` | `empl_` | Employee-organization relationships over time |
| `reporting_relationship` | `rr_` | Manager-subordinate relationships |
| `career_event` | `ce_` | Career milestones (join, leave, promotion, etc.) |
| `event_log` | `evt_` | Immutable audit log with hash chaining |
| `reporting_claim` | `claim_` | Crowdsourced relationship claims |
| `claim_evidence` | `evi_` | Evidence supporting/refuting claims |
| `contributor_score` | `cs_` | Per-actor scoring and visibility levels |

### Migrations

```bash
# Create a new migration
poetry run alembic revision --autogenerate -m "description"

# Apply migrations
make migrate
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | Octopod Backend | Application display name |
| `DEBUG` | true | Enable debug mode and verbose SQL logging |
| `ENVIRONMENT` | development | Runtime environment |
| `HOST` | 0.0.0.0 | Server bind host |
| `PORT` | 8000 | Server bind port |
| `POSTGRES_USER` | octopod | PostgreSQL username |
| `POSTGRES_PASSWORD` | octopod | PostgreSQL password |
| `POSTGRES_DB` | octopod_db | PostgreSQL database name |
| `POSTGRES_HOST` | db | PostgreSQL host (`db` for Docker, `localhost` for local) |
| `POSTGRES_PORT` | 5432 | PostgreSQL port |
| `SECRET_KEY` | change-me-in-production | JWT secret key |
| `ALGORITHM` | HS256 | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 30 | Token expiry time |
| `ALLOWED_ORIGINS` | ["*"] | CORS allowed origins |

## Tech Stack

- **FastAPI** -- Async web framework
- **SQLAlchemy 2.0** -- Async ORM with PostgreSQL (asyncpg) and SQLite (aiosqlite for tests)
- **Pydantic v2** -- Request/response validation
- **Alembic** -- Database migrations
- **Poetry** -- Dependency management
- **Docker Compose** -- Container orchestration (app + PostgreSQL + pgAdmin)
- **pytest** + **pytest-asyncio** -- Testing framework
- **Black** + **isort** + **Ruff** -- Code formatting and linting

## Developer Profile Ingestion & Search

Octopod includes a developer profiling system that pulls data from **GitHub**, **LinkedIn** (via Proxycurl), and **HuggingFace**, merges it into a cohesive profile, computes ranking scores, and enables semantic search via **Qdrant** vector DB.

### Setup

**1. Start infrastructure:**

```bash
docker compose up db qdrant -d
```

This adds a Qdrant vector database (http://localhost:6333/dashboard) alongside PostgreSQL.

**2. Configure API keys** in `.env`:

```env
# Required for GitHub (60 req/hr without, 5000/hr with)
GITHUB_TOKEN=ghp_your_personal_access_token

# Required for LinkedIn profiles (paid API - https://nubela.co/proxycurl)
PROXYCURL_API_KEY=your_key_here

# Optional for HuggingFace (public API works without)
HUGGINGFACE_TOKEN=hf_your_token_here

# Qdrant (defaults work with docker compose)
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

> **Minimum to start:** Just `GITHUB_TOKEN`. Create a free personal access token at https://github.com/settings/tokens (no special scopes needed — public data only).

**3. Install dependencies and start:**

```bash
poetry install
poetry run alembic upgrade head
make dev
```

### Usage Flow

```bash
# 1. Create a developer profile
curl -X POST http://localhost:8000/api/v1/developer-profile \
  -H "Content-Type: application/json" \
  -d '{"github_username": "torvalds", "auto_ingest": true}'

# 2. Check ingestion status
curl http://localhost:8000/api/v1/developer-profile/{id}/status

# 3. Merge platform data into a cohesive profile
curl -X POST http://localhost:8000/api/v1/developer-profile/{id}/merge

# 4. Get the merged profile
curl http://localhost:8000/api/v1/developer-profile/{id}/cohesive

# 5. Get ranking scores
curl http://localhost:8000/api/v1/developer-profile/{id}/ranking

# 6. Semantic search
curl -X POST http://localhost:8000/api/v1/developer-profile/search \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning engineer with Python", "limit": 10}'
```

### Enriching profiles over time

You can add platform identifiers later and re-ingest — data is merged, not replaced:

```bash
# Add LinkedIn to an existing profile
curl -X PATCH http://localhost:8000/api/v1/developer-profile/{id} \
  -H "Content-Type: application/json" \
  -d '{"linkedin_url": "https://linkedin.com/in/someone"}'

# Re-ingest (fetches all configured platforms)
curl -X POST http://localhost:8000/api/v1/developer-profile/{id}/ingest

# Re-merge (combines all sources with priority rules)
curl -X POST http://localhost:8000/api/v1/developer-profile/{id}/merge
```

### Developer Profile Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/developer-profile` | Create profile with platform identifiers |
| GET | `/developer-profile` | List profiles (paginated) |
| GET | `/developer-profile/{id}` | Get profile by ID |
| PATCH | `/developer-profile/{id}` | Update platform identifiers |
| POST | `/developer-profile/{id}/ingest` | Trigger ingestion (202) |
| GET | `/developer-profile/{id}/status` | Check ingestion status |
| GET | `/developer-profile/{id}/cohesive` | Get merged profile |
| POST | `/developer-profile/{id}/merge` | Force re-merge |
| GET | `/developer-profile/{id}/ranking` | Get ranking scores |
| POST | `/developer-profile/rank` | Rank profiles with custom weights |
| POST | `/developer-profile/search` | Semantic search |

### Merge Priority Rules

When multiple platforms provide the same field, the winner is determined by:

| Field | Priority |
|-------|----------|
| display_name, bio, headline | LinkedIn > GitHub > HuggingFace |
| avatar_url | GitHub > LinkedIn > HuggingFace |
| company | LinkedIn > GitHub |
| skills | Union of all sources |
| languages | GitHub (from repo stats) |
| job_history | LinkedIn (authoritative) |

### Ranking Scores

8 component scores (each 0.0–1.0) combined into a weighted composite:

| Component | Weight | Key Inputs |
|-----------|--------|------------|
| github_activity | 0.20 | contributions, repos |
| technical_influence | 0.15 | stars, followers, downloads |
| hiring_fit | 0.15 | skills, title, company |
| experience | 0.15 | years of experience |
| skills_breadth | 0.10 | unique skills + languages |
| recency | 0.10 | days since last activity |
| oss_contribution | 0.10 | non-fork repos, topics |
| hf_impact | 0.05 | models, datasets, downloads |

Weights are customizable via the `/rank` endpoint.

## API Documentation

When running the application, interactive API documentation is available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
