import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from app.db.base import Base  # noqa: E402
from app.settings import settings  # noqa: E402

# Import all models so Base.metadata knows about them
from app.model.career_event_model import CareerEvent  # noqa: E402, F401
from app.model.claim_evidence_model import ClaimEvidence  # noqa: E402, F401
from app.model.contributor_score_model import ContributorScore  # noqa: E402, F401
from app.model.employee_model import Employee  # noqa: E402, F401
from app.model.employment_model import Employment  # noqa: E402, F401
from app.model.event_log_model import EventLog  # noqa: E402, F401
from app.model.organization_model import Organization  # noqa: E402, F401
from app.model.reporting_claim_model import ReportingClaim  # noqa: E402, F401
from app.model.reporting_relationship_model import ReportingRelationship  # noqa: E402, F401

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata

# Override sqlalchemy.url with value from settings
config.set_main_option("sqlalchemy.url", settings.sync_database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
