"""Add subscription and billing_event tables for Stripe billing.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscription",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("org_id", sa.String(), nullable=False),
        sa.Column("stripe_customer_id", sa.String(255), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("plan", sa.String(30), nullable=False, server_default="free"),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("seat_count", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("current_period_start", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "cancel_at_period_end", sa.String(5), nullable=False, server_default="false"
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_subscription_org_id", "subscription", ["org_id"], unique=True)
    op.create_index("ix_subscription_stripe_customer_id", "subscription", ["stripe_customer_id"])
    op.create_index(
        "ix_subscription_stripe_subscription_id",
        "subscription",
        ["stripe_subscription_id"],
        unique=True,
    )

    op.create_table(
        "billing_event",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("stripe_event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("org_id", sa.String(), nullable=True),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_billing_event_stripe_event_id", "billing_event", ["stripe_event_id"], unique=True
    )
    op.create_index("ix_billing_event_org_id", "billing_event", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_billing_event_org_id", table_name="billing_event")
    op.drop_index("ix_billing_event_stripe_event_id", table_name="billing_event")
    op.drop_table("billing_event")
    op.drop_index("ix_subscription_stripe_subscription_id", table_name="subscription")
    op.drop_index("ix_subscription_stripe_customer_id", table_name="subscription")
    op.drop_index("ix_subscription_org_id", table_name="subscription")
    op.drop_table("subscription")
