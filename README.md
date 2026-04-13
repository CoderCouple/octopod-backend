# Octopod Backend

A FastAPI-based backend service for the Octopod application.

## Features

- FastAPI web framework
- PostgreSQL with SQLAlchemy ORM
- MongoDB support with Motor
- Async/await support throughout
- Alembic for database migrations
- Pre-commit hooks for code quality
- Docker support
- Comprehensive testing with pytest

## Prerequisites

- Python 3.11+
- Poetry for dependency management
- PostgreSQL (optional, for database features)
- MongoDB (optional, for document storage)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd octopod-backend
```

2. Install dependencies:
```bash
poetry install
```

3. Copy environment variables:
```bash
cp .env.example .env
```

4. Set up pre-commit hooks:
```bash
make pre-commit
```

## Development

Run the development server with hot reload:
```bash
make dev
```

The API will be available at `http://localhost:8000`
API documentation: `http://localhost:8000/docs`

## Available Commands

```bash
make help        # Show all available commands
make install     # Install dependencies
make dev         # Run development server
make run         # Run production server
make test        # Run tests
make lint        # Run linters
make format      # Format code
make clean       # Clean cache files
make migrate     # Run database migrations
```

## Project Structure

```
octopod-backend/
├── app/
│   ├── api/         # API endpoints
│   ├── common/      # Common utilities
│   ├── db/          # Database models and configuration
│   ├── middleware/  # Custom middleware
│   ├── model/       # Pydantic models
│   ├── service/     # Business logic
│   ├── main.py      # Application entry point
│   └── settings.py  # Configuration management
├── tests/           # Test files
├── alembic/         # Database migrations
├── pyproject.toml   # Project dependencies
├── Makefile         # Common commands
└── README.md        # This file
```

## Testing

Run all tests:
```bash
make test
```

Run tests with coverage:
```bash
poetry run pytest --cov=app tests/
```

## Code Quality

Format code:
```bash
make format
```

Run linters:
```bash
make lint
```

## Database Migrations

Create a new migration:
```bash
poetry run alembic revision --autogenerate -m "Description"
```

Apply migrations:
```bash
make migrate
```

## Environment Variables

See `.env.example` for all available configuration options.

Key variables:
- `ENVIRONMENT`: development/staging/production
- `DEBUG`: Enable debug mode
- `DATABASE_URL`: PostgreSQL connection string
- `MONGODB_URL`: MongoDB connection string
- `SECRET_KEY`: Application secret key

## API Documentation

When running the application, interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## License

[Your License]