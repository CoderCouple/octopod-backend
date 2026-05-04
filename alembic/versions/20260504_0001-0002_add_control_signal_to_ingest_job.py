"""add control_signal to ingest_job

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-04
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE ingest_job ADD COLUMN IF NOT EXISTS "
        "control_signal VARCHAR(10) NOT NULL DEFAULT 'none'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE ingest_job DROP COLUMN IF EXISTS control_signal")
