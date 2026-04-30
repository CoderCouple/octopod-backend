# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
- **Name**: octopod-backend
- **Version**: 0.1.0
- **Python Version**: >=3.11
- **Framework**: FastAPI
- **Build System**: Poetry

## Common Development Tasks

### Running the Application
```bash
make dev         # Run development server with hot reload
make run         # Run production server
```

### Code Quality
```bash
make lint        # Run ruff linter
make format      # Format code with black, isort, and ruff
make test        # Run pytest tests
```

### Database Operations
```bash
make migrate     # Apply database migrations
poetry run alembic revision --autogenerate -m "description"  # Create new migration
```

### Setup Commands
```bash
poetry install           # Install all dependencies
make pre-commit         # Install pre-commit hooks
make pre-commit-run     # Run pre-commit on all files
```

## Project Structure
```
octopod-backend/
├── app/
│   ├── api/         # API endpoints and routes
│   ├── common/      # Shared utilities and helpers
│   ├── db/          # Database models, sessions, and base configurations
│   ├── middleware/  # Custom middleware components
│   ├── model/       # Pydantic models for request/response schemas
│   ├── service/     # Business logic and service layer
│   ├── main.py      # FastAPI application initialization
│   └── settings.py  # Application configuration using pydantic-settings
├── tests/           # Test files using pytest
├── alembic/         # Database migration scripts
└── pyproject.toml   # Project dependencies and tool configurations
```

## Architecture Patterns

### Database
- Uses SQLAlchemy 2.0 with async support
- PostgreSQL for relational data (asyncpg driver)
- Alembic for schema migrations

### API Structure
- RESTful endpoints under `/api/v1` prefix
- Health checks at `/api/v1/health` and `/api/v1/ready`
- FastAPI dependency injection for database sessions
- Pydantic for request/response validation

### Testing
- pytest with async support (pytest-asyncio)
- Test fixtures in conftest.py
- In-memory SQLite for test database

### Code Style
- Black formatter with 100 char line length
- isort with black profile
- Ruff for linting with comprehensive rule set
- Pre-commit hooks for automatic formatting