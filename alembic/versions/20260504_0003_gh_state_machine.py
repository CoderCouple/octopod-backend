"""gh state machine — evolve gh_checkpoints, add gh_org_checkpoints

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-04

Adds discovered_at, source, org_source to gh_checkpoints.
Migrates status values: success -> ingested, pending -> failed.
Creates gh_org_checkpoints table for org-level discovery tracking.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    raw = conn.connection.dbapi_connection
    cur = raw.cursor()

    # 1. Add new columns to gh_checkpoints
    cur.execute(
        "ALTER TABLE gh_checkpoints "
        "ADD COLUMN IF NOT EXISTS discovered_at TIMESTAMPTZ, "
        "ADD COLUMN IF NOT EXISTS source TEXT, "
        "ADD COLUMN IF NOT EXISTS org_source TEXT"
    )

    # 2. Migrate existing status values
    cur.execute("UPDATE gh_checkpoints SET status = 'ingested' WHERE status = 'success'")
    cur.execute("UPDATE gh_checkpoints SET status = 'failed' WHERE status = 'pending'")

    # 3. Create gh_org_checkpoints table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS gh_org_checkpoints (
            org_login       TEXT PRIMARY KEY,
            status          TEXT NOT NULL DEFAULT 'pending',
            member_count    INT,
            discovered_at   TIMESTAMPTZ,
            last_fetched_at TIMESTAMPTZ,
            last_job_id     TEXT
        )
    """)


def downgrade() -> None:
    conn = op.get_bind()
    raw = conn.connection.dbapi_connection
    cur = raw.cursor()

    # Revert status values
    cur.execute("UPDATE gh_checkpoints SET status = 'success' WHERE status = 'ingested'")
    cur.execute("UPDATE gh_checkpoints SET status = 'pending' WHERE status = 'failed'")

    # Drop new columns
    cur.execute(
        "ALTER TABLE gh_checkpoints "
        "DROP COLUMN IF EXISTS discovered_at, "
        "DROP COLUMN IF EXISTS source, "
        "DROP COLUMN IF EXISTS org_source"
    )

    cur.execute("DROP TABLE IF EXISTS gh_org_checkpoints")
