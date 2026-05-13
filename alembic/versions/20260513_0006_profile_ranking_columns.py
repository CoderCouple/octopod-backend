"""Add missing score columns to profile_ranking.

The profile_ranking table predates these score columns. The model already
references them, so searches that JOIN profile_ranking fail with
``UndefinedColumnError``. Add the columns idempotently so existing rows
keep their defaults.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


SCORE_COLS = [
    "github_activity_score",
    "technical_influence_score",
    "hiring_fit_score",
    "experience_score",
    "skills_breadth_score",
    "recency_score",
    "oss_contribution_score",
    "hf_impact_score",
    "composite_score",
]


def upgrade() -> None:
    for col in SCORE_COLS:
        op.execute(
            f"ALTER TABLE profile_ranking ADD COLUMN IF NOT EXISTS "
            f"{col} NUMERIC(5, 4) DEFAULT 0"
        )
    op.execute(
        "ALTER TABLE profile_ranking ADD COLUMN IF NOT EXISTS "
        "weight_config JSONB DEFAULT '{}'::jsonb"
    )
    op.execute(
        "ALTER TABLE profile_ranking ADD COLUMN IF NOT EXISTS "
        "computed_at TIMESTAMPTZ DEFAULT NOW()"
    )


def downgrade() -> None:
    for col in SCORE_COLS:
        op.execute(f"ALTER TABLE profile_ranking DROP COLUMN IF EXISTS {col}")
    op.execute("ALTER TABLE profile_ranking DROP COLUMN IF EXISTS weight_config")
    op.execute("ALTER TABLE profile_ranking DROP COLUMN IF EXISTS computed_at")
