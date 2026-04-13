.PHONY: help install dev run test lint format clean migrate docker-up docker-down docker-build docker-logs docker-db

help:
	@echo "Available commands:"
	@echo "  install       Install dependencies"
	@echo "  dev           Run development server"
	@echo "  run           Run production server"
	@echo "  test          Run tests"
	@echo "  lint          Run linters"
	@echo "  format        Format code"
	@echo "  clean         Clean cache files"
	@echo "  migrate       Run database migrations"
	@echo ""
	@echo "Docker commands:"
	@echo "  docker-up     Start all services"
	@echo "  docker-down   Stop all services"
	@echo "  docker-build  Build and start all services"
	@echo "  docker-logs   Tail logs"
	@echo "  docker-db     Start only PostgreSQL + pgAdmin"

install:
	poetry install

dev:
	poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run:
	poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000

test:
	poetry run pytest tests/ -v

lint:
	poetry run ruff check .
	poetry run mypy app/

format:
	poetry run black .
	poetry run isort .
	poetry run ruff check --fix .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +

migrate:
	poetry run alembic upgrade head

pre-commit:
	poetry run pre-commit install

pre-commit-run:
	poetry run pre-commit run --all-files

# Docker commands
docker-up:
	docker-compose up

docker-down:
	docker-compose down

docker-build:
	docker-compose up --build

docker-logs:
	docker-compose logs -f

docker-db:
	docker-compose up db pgadmin