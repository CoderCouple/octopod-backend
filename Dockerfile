FROM python:3.11-slim

ENV POETRY_VERSION=1.8.0 \
    POETRY_VIRTUALENVS_CREATE=false \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for psycopg/asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
 && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --upgrade pip \
    && pip install poetry==$POETRY_VERSION

# Copy project files and install
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --without dev

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
