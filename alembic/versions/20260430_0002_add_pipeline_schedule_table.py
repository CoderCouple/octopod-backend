"""add pipeline_schedule table

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("pipeline_schedule"):
        op.create_table(
            "pipeline_schedule",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("pipeline_type", sa.String(length=100), nullable=False),
            sa.Column(
                "input_params",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column("cron_expression", sa.String(length=100), nullable=False),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("last_run_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("next_run_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_pipeline_schedule_pipeline_type"),
            "pipeline_schedule",
            ["pipeline_type"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_pipeline_schedule_pipeline_type"), table_name="pipeline_schedule"
    )
    op.drop_table("pipeline_schedule")
