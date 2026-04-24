# Octopod Backend

A B2B SaaS platform for developer intelligence — ingesting profiles from **GitHub**, **HuggingFace**, and **LinkedIn**, merging them into cohesive identities, computing ranking scores, and enabling semantic search. Includes a multi-step email outreach system and a crowdsourced org graph.

Built with **FastAPI**, **PostgreSQL**, **Qdrant** vector DB, and **asyncpg**.

## Architecture

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
- **Model layer** defines SQLAlchemy ORM models with prefixed UUIDs (e.g. `org_`, `emp_`, `ij_`)
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
│   │       │   ├── developer_profile_api.py  # Profile CRUD, ingest, search, ranking
│   │       │   ├── ingest_source_api.py      # GH/HF/LN discover + run (6 endpoints)
│   │       │   ├── ingest_job_api.py         # Job monitoring, status, retry (7 endpoints)
│   │       │   ├── ingest_pipeline_api.py    # Pipeline execution, sync, embed (10 endpoints)
│   │       │   ├── ingest_schedule_api.py    # Schedule CRUD (4 endpoints)
│   │       │   ├── ingest_identity_api.py    # Identity resolution (6 endpoints)
│   │       │   ├── mailbox_api.py            # Email mailbox management
│   │       │   ├── email_template_api.py     # Email template CRUD
│   │       │   ├── email_campaign_api.py     # Campaign lifecycle
│   │       │   ├── email_tracking_api.py     # Open/click tracking pixels
│   │       │   └── email_enrichment_api.py   # Email discovery for profiles
│   │       ├── request/                 # Pydantic request schemas
│   │       └── response/               # Pydantic response schemas
│   ├── common/
│   │   ├── auth/auth.py                 # Actor ID extraction from headers
│   │   ├── enum/                        # Enums (ingest job types, claim states, etc.)
│   │   ├── ingest_common.py             # Shared ingest helpers
│   │   ├── exceptions.py               # Custom HTTP exceptions
│   │   ├── hashing.py                   # SHA-256 event hash computation
│   │   └── pagination.py               # Generic pagination params/response
│   ├── db/
│   │   ├── base.py                      # SQLAlchemy DeclarativeBase
│   │   ├── engine.py                    # Async/sync engine factories (cached)
│   │   ├── session.py                   # get_db() async session dependency
│   │   ├── qdrant_client.py             # Qdrant vector DB client
│   │   └── repository/                  # Data access repositories
│   ├── ingest/                          # Ingestion pipeline
│   │   ├── gh/                          # GitHub: client, config, discover, orchestrator, storage
│   │   ├── hf/                          # HuggingFace: client, config, discover, orchestrator, storage
│   │   ├── ln/                          # LinkedIn: client (Proxycurl), config, discover, orchestrator
│   │   ├── bridge/                      # Bridge sync: raw -> domain -> cohesive profiles
│   │   │   ├── orchestrator.py          # Bridge sync orchestrator
│   │   │   ├── storage.py               # Profile merge, aggregation, indexing
│   │   │   ├── resolver.py              # Identity resolution (cross-platform dedup)
│   │   │   └── indexer.py               # Dual indexer (Qdrant + OpenSearch)
│   │   ├── pipeline/                    # Pipeline orchestration
│   │   │   ├── runner.py                # Step-based pipeline runner
│   │   │   ├── tracker.py               # Execution tracking (pause/resume/cancel)
│   │   │   ├── steps.py                 # Pipeline step definitions
│   │   │   ├── scheduler.py             # Cron-based pipeline scheduler
│   │   │   └── embed.py                 # Batch embedding to Qdrant
│   │   ├── common/
│   │   │   └── job_tracker.py           # DB-backed job tracking (ingest_job + ingest_job_item)
│   │   └── cli.py                       # CLI for running ingestion
│   ├── model/                           # SQLAlchemy ORM models
│   ├── service/                         # Business logic services
│   │   ├── embedding/                   # Sentence transformer provider
│   │   ├── campaign_service.py          # Email campaign orchestration
│   │   ├── mailbox_service.py           # Mailbox management
│   │   ├── email_enrichment_service.py  # Email discovery
│   │   ├── graph_service.py             # Org graph + DFS cycle detection
│   │   └── ...                          # Other services
│   ├── outreach/                        # Email sending infrastructure
│   └── middleware/
│       └── actor_context.py             # Actor context middleware
├── tests/                               # pytest test suite
├── sql/
│   └── schema.sql                       # PostgreSQL schema + seed data
├── docs/                                # Architecture documentation
├── alembic/                             # Database migration scripts
├── docker-compose.yml                   # Docker services
├── Dockerfile                           # Python 3.11 + Poetry container
├── Makefile                             # Development commands
└── pyproject.toml                       # Poetry dependencies + tool configs
```

## Prerequisites

- **Python** >= 3.11
- **Poetry** >= 1.8
- **Docker** and **Docker Compose** (for containerized setup)

## Quick Start (Docker)

```bash
# 1. Clone and enter the project
cd octopod-backend

# 2. Copy the environment file
cp .env.example .env

# 3. Start all services (app + postgres + pgadmin + qdrant)
make docker-up

# 4. Verify it's running
curl http://localhost:8000/api/v1/health
```

This starts the following containers:

| Service | URL | Description |
|---------|-----|-------------|
| **web** | http://localhost:8000 | FastAPI application |
| **db** | localhost:5432 | PostgreSQL 16 |
| **pgadmin** | http://localhost:8080 | pgAdmin (admin@octopod.dev / octopod) |
| **qdrant** | http://localhost:6333/dashboard | Qdrant vector database |

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

The server starts at http://localhost:8000. Swagger docs at http://localhost:8000/docs.

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

## API Endpoints

All endpoints are under `/api/v1`. Interactive Swagger docs at `/docs`.

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/ready` | Readiness probe -- checks database and dependencies |

### Developer Profiles

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

### Ingestion -- Source Discovery & Run

| Method | Path | Description |
|--------|------|-------------|
| POST | `/ingest/gh/discover` | Discover top GitHub users by ranking |
| POST | `/ingest/gh/run` | Ingest GitHub profiles by login |
| POST | `/ingest/hf/discover` | Discover top HuggingFace authors |
| POST | `/ingest/hf/run` | Ingest HuggingFace profiles |
| POST | `/ingest/ln/discover` | Extract LinkedIn URLs from GH/HF data |
| POST | `/ingest/ln/run` | Ingest LinkedIn profiles via Proxycurl |

### Ingestion -- Job Monitoring

| Method | Path | Description |
|--------|------|-------------|
| GET | `/ingest/status` | Checkpoint summary (GH + HF counts) |
| POST | `/ingest/retry` | Retry failed ingestions |
| GET | `/ingest/jobs` | List jobs (filter by platform, status) |
| GET | `/ingest/jobs/{job_id}` | Job detail with item counts |
| GET | `/ingest/jobs/{job_id}/items` | Job items list |
| GET | `/ingest/jobs/{job_id}/data` | Ingested data for job |
| GET | `/ingest/jobs/{job_id}/data/{login}` | Single user data |

### Ingestion -- Pipeline

| Method | Path | Description |
|--------|------|-------------|
| POST | `/ingest/sync` | Trigger bridge sync (raw -> cohesive) |
| POST | `/ingest/embed` | Trigger batch embedding to Qdrant |
| POST | `/ingest/pipeline/start` | Start a pipeline (daily, weekly, seed, etc.) |
| GET | `/ingest/pipeline/active` | List running/paused pipelines |
| GET | `/ingest/pipeline/{execution_id}` | Execution detail with steps |
| POST | `/ingest/pipeline/{execution_id}/pause` | Pause pipeline |
| POST | `/ingest/pipeline/{execution_id}/resume` | Resume paused pipeline |
| POST | `/ingest/pipeline/{execution_id}/cancel` | Cancel pipeline |
| POST | `/ingest/pipeline/{execution_id}/rerun` | Rerun with same config |
| GET | `/ingest/pipeline/status` | Pipeline health dashboard |

### Ingestion -- Schedule

| Method | Path | Description |
|--------|------|-------------|
| POST | `/ingest/schedule` | Create a pipeline schedule (cron) |
| GET | `/ingest/schedules` | List all schedules |
| PUT | `/ingest/schedule/{id}` | Update a schedule |
| DELETE | `/ingest/schedule/{id}` | Delete a schedule |

### Ingestion -- Identity Resolution

| Method | Path | Description |
|--------|------|-------------|
| GET | `/ingest/identity/candidates` | List merge candidates |
| GET | `/ingest/identity/candidates/{id}` | Candidate detail with profiles |
| POST | `/ingest/identity/candidates/{id}/approve` | Approve and merge |
| POST | `/ingest/identity/candidates/{id}/reject` | Reject candidate |
| POST | `/ingest/identity/resolve` | Trigger resolution scan |
| GET | `/ingest/identity/stats` | Resolution stats |

### Email Outreach

| Method | Path | Description |
|--------|------|-------------|
| POST | `/mailbox/connect/smtp` | Connect SMTP mailbox |
| GET | `/mailbox` | List mailboxes |
| GET | `/mailbox/{id}` | Get mailbox detail |
| PATCH | `/mailbox/{id}` | Update mailbox settings |
| DELETE | `/mailbox/{id}` | Disconnect mailbox |
| POST | `/email-template` | Create email template |
| GET | `/email-template` | List templates |
| GET | `/email-template/{id}` | Get template |
| PATCH | `/email-template/{id}` | Update template |
| DELETE | `/email-template/{id}` | Delete template |
| POST | `/email-campaign` | Create campaign |
| GET | `/email-campaign` | List campaigns |
| GET | `/email-campaign/{id}` | Get campaign detail |
| POST | `/email-campaign/{id}/launch` | Launch campaign |
| POST | `/email-campaign/{id}/pause` | Pause campaign |
| POST | `/email-campaign/{id}/resume` | Resume campaign |
| POST | `/email-enrichment/batch` | Batch email discovery |

## Ingestion Pipeline

The ingestion system operates in stages:

```
1. Discover   ->  Find top users on GH/HF, extract LN URLs
2. Ingest     ->  Fetch full profiles + repos/models/datasets
3. Bridge Sync ->  Merge raw data into developer_profile + cohesive_individual_profile
4. Identity   ->  Cross-platform deduplication (email, name, username matching)
5. Embed      ->  Generate embeddings and index into Qdrant for search
```

Each stage is tracked via `ingest_job` + `ingest_job_item` tables with status, timing, and error details.

### Pipeline Types

| Type | Steps |
|------|-------|
| `daily` | GH discover -> GH ingest -> HF discover -> HF ingest -> Bridge sync -> Embed |
| `weekly` | Daily steps + LN discover -> LN ingest -> Identity resolve |
| `seed` | Full pipeline for initial data load |
| `gh_only` | GH discover -> GH ingest -> Bridge sync |
| `hf_only` | HF discover -> HF ingest -> Bridge sync |
| `ln_only` | LN discover -> LN ingest -> Bridge sync |

Full pipelines (`daily`, `weekly`, `seed`) block each other; individual platform runs can be parallel.

### Merge Priority Rules

When multiple platforms provide the same field:

| Field | Priority |
|-------|----------|
| display_name, bio, headline | LinkedIn > GitHub > HuggingFace |
| avatar_url | GitHub > LinkedIn > HuggingFace |
| company | LinkedIn > GitHub |
| skills | Union of all sources |
| languages | GitHub (from repo stats) |
| job_history | LinkedIn (authoritative) |

### Ranking Scores

8 component scores (each 0.0--1.0) combined into a weighted composite:

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

## Setup -- API Keys

Configure in `.env`:

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

> **Minimum to start:** Just `GITHUB_TOKEN`. Create a free personal access token at https://github.com/settings/tokens (no special scopes needed -- public data only).

## Database

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
| `GITHUB_TOKEN` | -- | GitHub personal access token |
| `PROXYCURL_API_KEY` | -- | Proxycurl API key for LinkedIn |
| `HUGGINGFACE_TOKEN` | -- | HuggingFace API token |
| `QDRANT_HOST` | localhost | Qdrant vector DB host |
| `QDRANT_PORT` | 6333 | Qdrant vector DB port |

## Tech Stack

- **FastAPI** -- Async web framework
- **SQLAlchemy 2.0** -- Async ORM with PostgreSQL (asyncpg) and SQLite (aiosqlite for tests)
- **asyncpg** -- Direct async PostgreSQL driver (used by ingestion pipeline)
- **Pydantic v2** -- Request/response validation
- **Qdrant** -- Vector database for semantic search
- **Sentence Transformers** -- Embedding generation
- **Alembic** -- Database migrations
- **Poetry** -- Dependency management
- **Docker Compose** -- Container orchestration (app + PostgreSQL + pgAdmin + Qdrant)
- **pytest** + **pytest-asyncio** -- Testing framework
- **Black** + **isort** + **Ruff** -- Code formatting and linting

## API Documentation

When running the application, interactive API documentation is available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
