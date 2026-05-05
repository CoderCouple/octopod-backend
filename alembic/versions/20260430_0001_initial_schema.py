"""initial schema — all tables

Revision ID: 0001
Revises:
Create Date: 2026-04-30

Creates all tables from sql/schema.sql in a single migration.
Uses CREATE TABLE IF NOT EXISTS so it is safe to run on existing databases.
"""

from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA_SQL = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"


def upgrade() -> None:
    sql = _SCHEMA_SQL.read_text()
    conn = op.get_bind()
    # Use the raw DBAPI connection so we can execute the full multi-statement SQL
    raw = conn.connection.dbapi_connection
    raw.cursor().execute(sql)


def downgrade() -> None:
    tables = [
        "merge_candidate",
        "email_unsubscribe",
        "email_event",
        "email_message",
        "campaign_recipient",
        "campaign_step",
        "email_campaign",
        "email_template",
        "mailbox",
        "profile_ranking",
        "cohesive_individual_profile",
        "aggregated_individual_profile",
        "merge_audit_log",
        "social_profile",
        "developer_profile",
        "ingest_job_item",
        "ingest_job",
        "pipeline_schedule",
        "pipeline_execution_step",
        "pipeline_execution",
        "ln_checkpoints",
        "ln_users",
        "ln_pending_urls",
        "hf_checkpoints",
        "hf_datasets",
        "hf_models",
        "hf_users",
        "gh_checkpoints",
        "gh_activity_events",
        "gh_commits",
        "gh_repositories",
        "gh_users",
    ]
    for t in tables:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
