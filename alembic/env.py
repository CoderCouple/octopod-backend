import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from app.db.base import Base  # noqa: E402

# Import all models so Base.metadata knows about them
from app.model.aggregated_individual_profile_model import (
    AggregatedIndividualProfile,  # noqa: E402, F401
)
from app.model.billing_event_model import BillingEvent  # noqa: E402, F401
from app.model.campaign_recipient_model import CampaignRecipient  # noqa: E402, F401
from app.model.campaign_step_model import CampaignStep  # noqa: E402, F401
from app.model.cohesive_individual_profile_model import (
    CohesiveIndividualProfile,  # noqa: E402, F401
)
from app.model.developer_profile_model import DeveloperProfile  # noqa: E402, F401
from app.model.email_campaign_model import EmailCampaign  # noqa: E402, F401
from app.model.email_event_model import EmailEvent  # noqa: E402, F401
from app.model.email_message_model import EmailMessage  # noqa: E402, F401
from app.model.email_template_model import EmailTemplate  # noqa: E402, F401
from app.model.email_unsubscribe_model import EmailUnsubscribe  # noqa: E402, F401
from app.model.mailbox_model import Mailbox  # noqa: E402, F401
from app.model.merge_audit_log_model import MergeAuditLog  # noqa: E402, F401
from app.model.org_membership_model import OrgMembership  # noqa: E402, F401
from app.model.organization_model import Organization  # noqa: E402, F401
from app.model.profile_ranking_model import ProfileRanking  # noqa: E402, F401
from app.model.project_model import Project  # noqa: E402, F401
from app.model.social_profile_model import SocialProfile  # noqa: E402, F401
from app.model.subscription_model import Subscription  # noqa: E402, F401
from app.model.user_model import User  # noqa: E402, F401
from app.settings import settings  # noqa: E402

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata

# Override sqlalchemy.url with value from settings.
# Escape `%` to `%%` because alembic uses ConfigParser interpolation, and our
# URL-encoded DB password may contain `%`-sequences (e.g. `%5D` for `]`).
config.set_main_option("sqlalchemy.url", settings.sync_database_url.replace("%", "%%"))


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
