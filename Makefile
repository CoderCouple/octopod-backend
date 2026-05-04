.PHONY: help install dev run test lint format clean migrate docker-up docker-down docker-build docker-logs docker-db gh-init-schema hf-init-schema gh-discover gh-ingest hf-discover hf-ingest ingest-status embed-profiles job-pause job-resume job-cancel

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
	@echo ""
	@echo "AWS commands:"
	@echo "  db-tunnel     SSM tunnel to AWS RDS → localhost:5433"

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

# Ingestion commands
gh-init-schema:
	poetry run python -m app.ingest.cli gh-init-schema

hf-init-schema:
	poetry run python -m app.ingest.cli hf-init-schema

gh-discover:
	poetry run python -m app.ingest.cli gh-discover --top 5000 --output data/gh_logins.tsv

gh-ingest:
	poetry run python -m app.ingest.cli gh-ingest --input data/gh_logins.tsv

hf-discover:
	poetry run python -m app.ingest.cli hf-discover --top 5000 --output data/hf_users.tsv

hf-ingest:
	poetry run python -m app.ingest.cli hf-ingest --input data/hf_users.tsv

ingest-status:
	poetry run python -m app.ingest.cli status

job-pause:
	@test -n "$(JOB_ID)" || (echo "Usage: make job-pause JOB_ID=ij_xxx" && exit 1)
	poetry run python -m app.ingest.cli job-pause $(JOB_ID)

job-resume:
	@test -n "$(JOB_ID)" || (echo "Usage: make job-resume JOB_ID=ij_xxx" && exit 1)
	poetry run python -m app.ingest.cli job-resume $(JOB_ID)

job-cancel:
	@test -n "$(JOB_ID)" || (echo "Usage: make job-cancel JOB_ID=ij_xxx" && exit 1)
	poetry run python -m app.ingest.cli job-cancel $(JOB_ID)

embed-profiles:
	@echo "Triggering batch embedding of all profiles..."
	curl -s -X POST "http://localhost:8000/api/v1/developer-profile/embed-all?force=true" | python -m json.tool

# AWS DB tunnel (SSM port-forwarding to RDS)
db-tunnel:
	@echo "Opening SSM tunnel → localhost:5433 → RDS:5432"
	@echo "DataGrip: host=localhost port=5433 db=octopod_db user=dbadmin"
	@echo "Press Ctrl+C to close tunnel"
	aws ssm start-session \
		--target i-0d068f49ef729f538 \
		--document-name AWS-StartPortForwardingSessionToRemoteHost \
		--parameters '{"host":["octopodai-dev-postgress-db-stack-rdsdbinstance-rzqxkz9nu7pl.chq0wu4euqqh.us-west-2.rds.amazonaws.com"],"portNumber":["5432"],"localPortNumber":["5433"]}' \
		--region us-west-2