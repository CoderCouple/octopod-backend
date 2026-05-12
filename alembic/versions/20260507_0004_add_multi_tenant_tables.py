"""Add multi-tenant tables: organization, user, org_membership, project.
Add project_id to existing resource tables.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-07
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Create organization table ---
    op.create_table(
        "organization",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False, unique=True),
        sa.Column("plan", sa.String(30), nullable=False, server_default="free"),
        sa.Column("logo_url", sa.String(2048), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("updated_by", sa.String(), nullable=True),
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
    op.create_index("ix_organization_slug", "organization", ["slug"])

    # --- Create user table ---
    op.create_table(
        "user",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("cognito_sub", sa.String(), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(2048), nullable=True),
        sa.Column("default_org_id", sa.String(), nullable=True),
        sa.Column("default_project_id", sa.String(), nullable=True),
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
    op.create_index("ix_user_cognito_sub", "user", ["cognito_sub"])
    op.create_index("ix_user_email", "user", ["email"])

    # --- Create org_membership table ---
    op.create_table(
        "org_membership",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("org_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(30), nullable=False, server_default="member"),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("invited_by", sa.String(), nullable=True),
        sa.Column("invited_email", sa.String(320), nullable=True),
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
        sa.UniqueConstraint("org_id", "user_id", name="uq_org_membership_org_user"),
    )
    op.create_index("ix_org_membership_org_id", "org_membership", ["org_id"])
    op.create_index("ix_org_membership_user_id", "org_membership", ["user_id"])

    # --- Create project table ---
    op.create_table(
        "project",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("org_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("updated_by", sa.String(), nullable=True),
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
        sa.UniqueConstraint("org_id", "slug", name="uq_project_org_slug"),
    )
    op.create_index("ix_project_org_id", "project", ["org_id"])

    # --- Add project_id to existing resource tables ---
    for table_name in ("mailbox", "email_campaign", "email_template", "developer_profile"):
        op.add_column(table_name, sa.Column("project_id", sa.String(), nullable=True))
        op.create_index(f"ix_{table_name}_project_id", table_name, ["project_id"])


def downgrade() -> None:
    for table_name in ("developer_profile", "email_template", "email_campaign", "mailbox"):
        op.drop_index(f"ix_{table_name}_project_id", table_name=table_name)
        op.drop_column(table_name, "project_id")

    op.drop_index("ix_project_org_id", table_name="project")
    op.drop_table("project")

    op.drop_index("ix_org_membership_user_id", table_name="org_membership")
    op.drop_index("ix_org_membership_org_id", table_name="org_membership")
    op.drop_table("org_membership")

    op.drop_index("ix_user_email", table_name="user")
    op.drop_index("ix_user_cognito_sub", table_name="user")
    op.drop_table("user")

    op.drop_index("ix_organization_slug", table_name="organization")
    op.drop_table("organization")
