"""CRM, provider operations, social interactions, chat, and notifications.

Revision ID: 0008_crm_social
Revises: 0007_settings_config
Create Date: 2026-11-12 13:20:35.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0008_crm_social"
down_revision: Union[str, Sequence[str], None] = "0007_settings_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Postgres ENUM types
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE funnel_stage AS ENUM (
            'Lead', 'Contacted', 'Qualified', 'Proposal', 'Negotiation', 'Won', 'Lost'
        );
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;
    """)
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE feedback_type AS ENUM (
            'bug', 'idea', 'ui-ux', 'other'
        );
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;
    """)
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE dow AS ENUM (
            'sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'
        );
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;
    """)

    # 2. activities
    op.create_table(
        "activities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=True),
        sa.Column("type", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_activities_opportunity_id"), "activities", ["opportunity_id"], unique=False)

    # 3. opportunities
    op.create_table(
        "opportunities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=True),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=True),
        sa.Column("currency", sa.Text(), nullable=True),
        sa.Column("stage", postgresql.ENUM("Lead", "Contacted", "Qualified", "Proposal", "Negotiation", "Won", "Lost", name="funnel_stage", create_type=False), nullable=False),
        sa.Column("probability", sa.Integer(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("assigned_to", sa.Uuid(), nullable=True),
        sa.Column("close_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_opportunities_customer_id"), "opportunities", ["customer_id"], unique=False)
    op.create_index(op.f("ix_opportunities_provider_id"), "opportunities", ["provider_id"], unique=False)

    # 4. opportunity_stage_history
    op.create_table(
        "opportunity_stage_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("from_stage", sa.Text(), nullable=True),
        sa.Column("to_stage", sa.Text(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("changed_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_opportunity_stage_history_opportunity_id"), "opportunity_stage_history", ["opportunity_id"], unique=False)

    # 5. provider_analytics
    op.create_table(
        "provider_analytics",
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("profile_views", sa.BigInteger(), nullable=False),
        sa.Column("contact_clicks", sa.BigInteger(), nullable=False),
        sa.Column("last_computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("provider_id"),
    )

    # 6. provider_availability_weekly
    op.create_table(
        "provider_availability_weekly",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("day_of_week", postgresql.ENUM("sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", name="dow", create_type=False), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 7. provider_blocked_dates
    op.create_table(
        "provider_blocked_dates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("blocked_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_provider_blocked_dates_user_id"), "provider_blocked_dates", ["user_id"], unique=False)

    # 8. provider_customer
    op.create_table(
        "provider_customer",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_provider_customer_customer_id"), "provider_customer", ["customer_id"], unique=False)
    op.create_index(op.f("ix_provider_customer_provider_id"), "provider_customer", ["provider_id"], unique=False)

    # 9. chat
    op.create_table(
        "chat",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("senderId", sa.Uuid(), nullable=False),
        sa.Column("receiverId", sa.Uuid(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("isRead", sa.Boolean(), nullable=False),
        sa.Column("senderUserType", sa.Text(), nullable=True),
        sa.Column("receiverUserType", sa.Text(), nullable=True),
        sa.Column("attachments", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_receiverId"), "chat", ["receiverId"], unique=False)
    op.create_index(op.f("ix_chat_senderId"), "chat", ["senderId"], unique=False)

    # 10. chat_inbox
    op.create_table(
        "chat_inbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("senderId", sa.Uuid(), nullable=False),
        sa.Column("receiverId", sa.Uuid(), nullable=False),
        sa.Column("lastMessage", sa.Text(), nullable=True),
        sa.Column("lastMessageTime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unreadCount", sa.Integer(), nullable=False),
        sa.Column("senderUserType", sa.Text(), nullable=True),
        sa.Column("receiverUserType", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_inbox_receiverId"), "chat_inbox", ["receiverId"], unique=False)
    op.create_index(op.f("ix_chat_inbox_senderId"), "chat_inbox", ["senderId"], unique=False)

    # 11. contact_messages
    op.create_table(
        "contact_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("first_name", sa.Text(), nullable=False),
        sa.Column("last_name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 12. feedback
    op.create_table(
        "feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("type", postgresql.ENUM("bug", "idea", "ui-ux", "other", name="feedback_type", create_type=False), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_feedback_user_id"), "feedback", ["user_id"], unique=False)

    # 13. notification
    op.create_table(
        "notification",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("type", sa.Text(), nullable=True),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("provider_id", sa.Uuid(), nullable=True),
        sa.Column("handyman_id", sa.Uuid(), nullable=True),
        sa.Column("booking_id", sa.Uuid(), nullable=True),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notification_customer_id"), "notification", ["customer_id"], unique=False)
    op.create_index(op.f("ix_notification_provider_id"), "notification", ["provider_id"], unique=False)

    # 14. notifications
    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("read", sa.Boolean(), nullable=False),
        sa.Column("type", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)

    # 15. review_customer
    op.create_table(
        "review_customer",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customerId", sa.Uuid(), nullable=True),
        sa.Column("serviceId", sa.Uuid(), nullable=True),
        sa.Column("providerId", sa.Uuid(), nullable=True),
        sa.Column("rating", sa.Numeric(), nullable=True),
        sa.Column("review", sa.Text(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_review_customer_serviceId"), "review_customer", ["serviceId"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_review_customer_serviceId"), table_name="review_customer")
    op.drop_table("review_customer")
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
    op.drop_table("notifications")
    op.drop_index(op.f("ix_notification_provider_id"), table_name="notification")
    op.drop_index(op.f("ix_notification_customer_id"), table_name="notification")
    op.drop_table("notification")
    op.drop_index(op.f("ix_feedback_user_id"), table_name="feedback")
    op.drop_table("feedback")
    op.drop_table("contact_messages")
    op.drop_index(op.f("ix_chat_inbox_senderId"), table_name="chat_inbox")
    op.drop_index(op.f("ix_chat_inbox_receiverId"), table_name="chat_inbox")
    op.drop_table("chat_inbox")
    op.drop_index(op.f("ix_chat_senderId"), table_name="chat")
    op.drop_index(op.f("ix_chat_receiverId"), table_name="chat")
    op.drop_table("chat")
    op.drop_index(op.f("ix_provider_customer_provider_id"), table_name="provider_customer")
    op.drop_index(op.f("ix_provider_customer_customer_id"), table_name="provider_customer")
    op.drop_table("provider_customer")
    op.drop_index(op.f("ix_provider_blocked_dates_user_id"), table_name="provider_blocked_dates")
    op.drop_table("provider_blocked_dates")
    op.drop_table("provider_availability_weekly")
    op.drop_table("provider_analytics")
    op.drop_index(op.f("ix_opportunity_stage_history_opportunity_id"), table_name="opportunity_stage_history")
    op.drop_table("opportunity_stage_history")
    op.drop_index(op.f("ix_opportunities_provider_id"), table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_customer_id"), table_name="opportunities")
    op.drop_table("opportunities")
    op.drop_index(op.f("ix_activities_opportunity_id"), table_name="activities")
    op.drop_table("activities")
    op.execute("DROP TYPE IF EXISTS dow CASCADE")
    op.execute("DROP TYPE IF EXISTS feedback_type CASCADE")
    op.execute("DROP TYPE IF EXISTS funnel_stage CASCADE")
