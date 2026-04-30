"""create email and outreach tables

Revision ID: 0001
Revises:
Create Date: 2026-04-28

Creates tables for the email outreach system that were missing from the database.
Only creates tables if they don't already exist (safe to re-run).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("mailbox"):
        op.create_table(
            "mailbox",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("owner_id", sa.String(), nullable=False),
            sa.Column("provider", sa.String(length=30), nullable=False),
            sa.Column("email_address", sa.String(length=320), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("access_token", sa.Text(), nullable=True),
            sa.Column("refresh_token", sa.Text(), nullable=True),
            sa.Column("token_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("smtp_host", sa.String(length=255), nullable=True),
            sa.Column("smtp_port", sa.Integer(), nullable=True),
            sa.Column("smtp_username", sa.String(length=255), nullable=True),
            sa.Column("smtp_password", sa.Text(), nullable=True),
            sa.Column("smtp_use_tls", sa.Boolean(), nullable=True),
            sa.Column("daily_send_limit", sa.Integer(), nullable=False),
            sa.Column("sends_today", sa.Integer(), nullable=False),
            sa.Column("sends_today_reset_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("warmup_enabled", sa.Boolean(), nullable=True),
            sa.Column("warmup_current_limit", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("last_error_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column(
                "metadata",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column("is_deleted", sa.Boolean(), nullable=False),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("updated_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_mailbox_owner_id"), "mailbox", ["owner_id"], unique=False)

    if not _table_exists("email_template"):
        op.create_table(
            "email_template",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("owner_id", sa.String(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("category", sa.String(length=100), nullable=True),
            sa.Column("subject", sa.Text(), nullable=False),
            sa.Column("body_html", sa.Text(), nullable=False),
            sa.Column("body_text", sa.Text(), nullable=True),
            sa.Column(
                "variables",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column(
                "metadata",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column("is_deleted", sa.Boolean(), nullable=False),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("updated_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_email_template_owner_id"), "email_template", ["owner_id"], unique=False
        )

    if not _table_exists("email_campaign"):
        op.create_table(
            "email_campaign",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("owner_id", sa.String(), nullable=False),
            sa.Column("mailbox_id", sa.String(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("send_window_start", sa.String(length=5), nullable=True),
            sa.Column("send_window_end", sa.String(length=5), nullable=True),
            sa.Column("send_timezone", sa.String(length=50), nullable=True),
            sa.Column(
                "send_days",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column("stop_on_reply", sa.Boolean(), nullable=True),
            sa.Column("stop_on_bounce", sa.Boolean(), nullable=True),
            sa.Column("track_opens", sa.Boolean(), nullable=True),
            sa.Column("track_clicks", sa.Boolean(), nullable=True),
            sa.Column("total_recipients", sa.Integer(), nullable=False),
            sa.Column("total_sent", sa.Integer(), nullable=False),
            sa.Column("total_delivered", sa.Integer(), nullable=False),
            sa.Column("total_opened", sa.Integer(), nullable=False),
            sa.Column("total_clicked", sa.Integer(), nullable=False),
            sa.Column("total_replied", sa.Integer(), nullable=False),
            sa.Column("total_bounced", sa.Integer(), nullable=False),
            sa.Column("total_unsubscribed", sa.Integer(), nullable=False),
            sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column(
                "metadata",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column("is_deleted", sa.Boolean(), nullable=False),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("updated_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_email_campaign_mailbox_id"), "email_campaign", ["mailbox_id"], unique=False
        )
        op.create_index(
            op.f("ix_email_campaign_owner_id"), "email_campaign", ["owner_id"], unique=False
        )

    if not _table_exists("campaign_step"):
        op.create_table(
            "campaign_step",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("campaign_id", sa.String(), nullable=False),
            sa.Column("template_id", sa.String(), nullable=True),
            sa.Column("step_order", sa.Integer(), nullable=False),
            sa.Column("step_type", sa.String(length=30), nullable=False),
            sa.Column("delay_days", sa.Integer(), nullable=False),
            sa.Column("delay_hours", sa.Integer(), nullable=False),
            sa.Column("subject_override", sa.Text(), nullable=True),
            sa.Column("body_override", sa.Text(), nullable=True),
            sa.Column("condition_field", sa.String(length=100), nullable=True),
            sa.Column("condition_op", sa.String(length=20), nullable=True),
            sa.Column("condition_value", sa.String(length=255), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("updated_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_campaign_step_campaign_id"), "campaign_step", ["campaign_id"], unique=False
        )

    if not _table_exists("campaign_recipient"):
        op.create_table(
            "campaign_recipient",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("campaign_id", sa.String(), nullable=False),
            sa.Column("developer_profile_id", sa.String(), nullable=True),
            sa.Column("email", sa.String(length=320), nullable=False),
            sa.Column("first_name", sa.String(length=255), nullable=True),
            sa.Column("last_name", sa.String(length=255), nullable=True),
            sa.Column("company", sa.String(length=255), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("current_step_order", sa.Integer(), nullable=False),
            sa.Column("next_send_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("email_source", sa.String(length=30), nullable=True),
            sa.Column(
                "merge_variables",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column(
                "metadata",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column("is_deleted", sa.Boolean(), nullable=False),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("updated_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_campaign_recipient_campaign_id"),
            "campaign_recipient",
            ["campaign_id"],
            unique=False,
        )

    if not _table_exists("email_message"):
        op.create_table(
            "email_message",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("campaign_id", sa.String(), nullable=False),
            sa.Column("step_id", sa.String(), nullable=False),
            sa.Column("recipient_id", sa.String(), nullable=False),
            sa.Column("mailbox_id", sa.String(), nullable=False),
            sa.Column("tracking_id", sa.String(), nullable=False),
            sa.Column("from_email", sa.String(length=320), nullable=False),
            sa.Column("from_name", sa.String(length=255), nullable=True),
            sa.Column("to_email", sa.String(length=320), nullable=False),
            sa.Column("subject", sa.Text(), nullable=False),
            sa.Column("body_html", sa.Text(), nullable=False),
            sa.Column("body_text", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("scheduled_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("delivered_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("opened_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("clicked_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("replied_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("bounced_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("failed_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("provider", sa.String(length=30), nullable=True),
            sa.Column("provider_message_id", sa.Text(), nullable=True),
            sa.Column("message_id_header", sa.Text(), nullable=True),
            sa.Column("thread_id", sa.Text(), nullable=True),
            sa.Column("in_reply_to", sa.Text(), nullable=True),
            sa.Column(
                "link_map",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column("open_count", sa.Integer(), nullable=False),
            sa.Column("click_count", sa.Integer(), nullable=False),
            sa.Column("retry_count", sa.Integer(), nullable=False),
            sa.Column("max_retries", sa.Integer(), nullable=False),
            sa.Column("next_retry_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "metadata",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tracking_id"),
        )
        op.create_index(
            op.f("ix_email_message_campaign_id"), "email_message", ["campaign_id"], unique=False
        )
        op.create_index(
            op.f("ix_email_message_recipient_id"), "email_message", ["recipient_id"], unique=False
        )

    if not _table_exists("email_event"):
        op.create_table(
            "email_event",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("message_id", sa.String(), nullable=False),
            sa.Column("event_type", sa.String(length=30), nullable=False),
            sa.Column("ip_address", sa.String(length=45), nullable=True),
            sa.Column("user_agent", sa.Text(), nullable=True),
            sa.Column("link_url", sa.Text(), nullable=True),
            sa.Column(
                "raw_payload",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_email_event_message_id"), "email_event", ["message_id"], unique=False
        )

    if not _table_exists("email_unsubscribe"):
        op.create_table(
            "email_unsubscribe",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("email", sa.String(length=320), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("source", sa.String(length=100), nullable=True),
            sa.Column("message_id", sa.String(), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email"),
        )

    if not _table_exists("social_profile"):
        op.create_table(
            "social_profile",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("developer_profile_id", sa.String(), nullable=False),
            sa.Column("platform", sa.String(length=30), nullable=False),
            sa.Column("username", sa.String(length=255), nullable=True),
            sa.Column("profile_url", sa.String(length=2048), nullable=True),
            sa.Column("display_name", sa.String(length=255), nullable=True),
            sa.Column("bio", sa.Text(), nullable=True),
            sa.Column("avatar_url", sa.String(length=2048), nullable=True),
            sa.Column("followers", sa.Integer(), nullable=True),
            sa.Column("following", sa.Integer(), nullable=True),
            sa.Column(
                "raw_data",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column("last_synced_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _table_exists("merge_audit_log"):
        op.create_table(
            "merge_audit_log",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("developer_profile_id", sa.String(), nullable=False),
            sa.Column("merge_level", sa.String(length=30), nullable=False),
            sa.Column("target_table", sa.String(length=60), nullable=False),
            sa.Column("merge_run_id", sa.String(), nullable=False),
            sa.Column("field_name", sa.String(length=100), nullable=False),
            sa.Column("winning_source", sa.String(length=30), nullable=False),
            sa.Column("winning_value", sa.Text(), nullable=True),
            sa.Column("previous_value", sa.Text(), nullable=True),
            sa.Column(
                "overridden_values",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column("action", sa.String(length=20), nullable=False),
            sa.Column("merged_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _table_exists("aggregated_individual_profile"):
        op.create_table(
            "aggregated_individual_profile",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("developer_profile_id", sa.String(), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=True),
            sa.Column("bio", sa.Text(), nullable=True),
            sa.Column("avatar_url", sa.String(length=2048), nullable=True),
            sa.Column("company", sa.String(length=255), nullable=True),
            sa.Column("location", sa.String(length=500), nullable=True),
            sa.Column("website", sa.String(length=2048), nullable=True),
            sa.Column("total_repos", sa.Integer(), nullable=True),
            sa.Column("total_stars", sa.Integer(), nullable=True),
            sa.Column("total_contributions", sa.Integer(), nullable=True),
            sa.Column("total_followers", sa.Integer(), nullable=True),
            sa.Column("total_hf_models", sa.Integer(), nullable=True),
            sa.Column("total_hf_datasets", sa.Integer(), nullable=True),
            sa.Column("total_hf_spaces", sa.Integer(), nullable=True),
            sa.Column("total_hf_downloads", sa.Integer(), nullable=True),
            sa.Column("total_papers", sa.Integer(), nullable=True),
            sa.Column(
                "languages",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column(
                "skills",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column(
                "topics",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column("headline", sa.Text(), nullable=True),
            sa.Column("current_title", sa.String(length=255), nullable=True),
            sa.Column("current_company", sa.String(length=255), nullable=True),
            sa.Column("industry", sa.String(length=255), nullable=True),
            sa.Column("years_of_experience", sa.Integer(), nullable=True),
            sa.Column(
                "job_history",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column(
                "education",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column(
                "certifications",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column("connections", sa.Integer(), nullable=True),
            sa.Column(
                "source_priority",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column("aggregated_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("developer_profile_id"),
        )

    if not _table_exists("cohesive_individual_profile"):
        op.create_table(
            "cohesive_individual_profile",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("developer_profile_id", sa.String(), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=True),
            sa.Column("bio", sa.Text(), nullable=True),
            sa.Column("headline", sa.Text(), nullable=True),
            sa.Column("location", sa.String(length=500), nullable=True),
            sa.Column("avatar_url", sa.String(length=2048), nullable=True),
            sa.Column("company", sa.String(length=255), nullable=True),
            sa.Column("website", sa.String(length=2048), nullable=True),
            sa.Column("total_repos", sa.Integer(), nullable=True),
            sa.Column("total_stars", sa.Integer(), nullable=True),
            sa.Column("total_contributions", sa.Integer(), nullable=True),
            sa.Column("total_followers", sa.Integer(), nullable=True),
            sa.Column("total_hf_models", sa.Integer(), nullable=True),
            sa.Column("total_hf_datasets", sa.Integer(), nullable=True),
            sa.Column("total_hf_spaces", sa.Integer(), nullable=True),
            sa.Column("total_hf_downloads", sa.Integer(), nullable=True),
            sa.Column("total_papers", sa.Integer(), nullable=True),
            sa.Column(
                "languages",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column(
                "skills",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column(
                "topics",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column("years_of_experience", sa.Integer(), nullable=True),
            sa.Column("current_title", sa.String(length=255), nullable=True),
            sa.Column("current_company", sa.String(length=255), nullable=True),
            sa.Column(
                "job_history",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column("embedding_text", sa.Text(), nullable=True),
            sa.Column(
                "search_tsv",
                sa.Text().with_variant(postgresql.TSVECTOR(), "postgresql"),
                nullable=True,
            ),
            sa.Column("embedding_vector_id", sa.String(length=255), nullable=True),
            sa.Column(
                "source_priority",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column("merged_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("developer_profile_id"),
        )

    if not _table_exists("profile_ranking"):
        op.create_table(
            "profile_ranking",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("cohesive_individual_profile_id", sa.String(), nullable=False),
            sa.Column("overall_score", sa.Integer(), nullable=False),
            sa.Column("github_score", sa.Integer(), nullable=True),
            sa.Column("huggingface_score", sa.Integer(), nullable=True),
            sa.Column("linkedin_score", sa.Integer(), nullable=True),
            sa.Column(
                "score_breakdown",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column("rank_position", sa.Integer(), nullable=True),
            sa.Column("scored_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("cohesive_individual_profile_id"),
        )


def downgrade() -> None:
    op.drop_table("profile_ranking")
    op.drop_table("cohesive_individual_profile")
    op.drop_table("aggregated_individual_profile")
    op.drop_table("merge_audit_log")
    op.drop_table("social_profile")
    op.drop_table("email_unsubscribe")
    op.drop_index(op.f("ix_email_event_message_id"), table_name="email_event")
    op.drop_table("email_event")
    op.drop_index(op.f("ix_email_message_recipient_id"), table_name="email_message")
    op.drop_index(op.f("ix_email_message_campaign_id"), table_name="email_message")
    op.drop_table("email_message")
    op.drop_index(op.f("ix_campaign_recipient_campaign_id"), table_name="campaign_recipient")
    op.drop_table("campaign_recipient")
    op.drop_index(op.f("ix_campaign_step_campaign_id"), table_name="campaign_step")
    op.drop_table("campaign_step")
    op.drop_index(op.f("ix_email_campaign_owner_id"), table_name="email_campaign")
    op.drop_index(op.f("ix_email_campaign_mailbox_id"), table_name="email_campaign")
    op.drop_table("email_campaign")
    op.drop_index(op.f("ix_email_template_owner_id"), table_name="email_template")
    op.drop_table("email_template")
    op.drop_index(op.f("ix_mailbox_owner_id"), table_name="mailbox")
    op.drop_table("mailbox")
