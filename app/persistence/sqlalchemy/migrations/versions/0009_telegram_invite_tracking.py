"""Telegram Bot invite tracking tables.

Revision ID: 0009_telegram_invite_tracking
Revises: 0008_crm_social
Create Date: 2026-11-13 11:50:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0009_telegram_invite_tracking"
down_revision: Union[str, Sequence[str], None] = "0008_crm_social"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. telegram_chats
    op.create_table(
        "telegram_chats",
        sa.Column("chat_id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # 2. telegram_users
    op.create_table(
        "telegram_users",
        sa.Column("user_id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("username", sa.Text(), nullable=True),
        sa.Column("first_name", sa.Text(), nullable=False),
        sa.Column("last_name", sa.Text(), nullable=True),
        sa.Column("is_bot", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_telegram_users_username", "telegram_users", ["username"], unique=False
    )

    # 3. telegram_invite_links
    op.create_table(
        "telegram_invite_links",
        sa.Column("invite_link", sa.Text(), primary_key=True, nullable=False),
        sa.Column(
            "chat_id",
            sa.BigInteger(),
            sa.ForeignKey("telegram_chats.chat_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "creator_user_id",
            sa.BigInteger(),
            sa.ForeignKey("telegram_users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("usage_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_telegram_invite_links_chat_id", "telegram_invite_links", ["chat_id"], unique=False
    )
    op.create_index(
        "ix_telegram_invite_links_creator_user_id",
        "telegram_invite_links",
        ["creator_user_id"],
        unique=False,
    )

    # 4. telegram_chat_members
    op.create_table(
        "telegram_chat_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "chat_id",
            sa.BigInteger(),
            sa.ForeignKey("telegram_chats.chat_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("telegram_users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "inviter_user_id",
            sa.BigInteger(),
            sa.ForeignKey("telegram_users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("invite_link", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("chat_id", "user_id", name="uq_telegram_chat_members_chat_user"),
    )
    op.create_index(
        "ix_telegram_chat_members_chat_id", "telegram_chat_members", ["chat_id"], unique=False
    )
    op.create_index(
        "ix_telegram_chat_members_user_id", "telegram_chat_members", ["user_id"], unique=False
    )
    op.create_index(
        "ix_telegram_chat_members_inviter_user_id",
        "telegram_chat_members",
        ["inviter_user_id"],
        unique=False,
    )

    # 5. telegram_invite_stats
    op.create_table(
        "telegram_invite_stats",
        sa.Column(
            "chat_id",
            sa.BigInteger(),
            sa.ForeignKey("telegram_chats.chat_id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("telegram_users.user_id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("total_invites", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("telegram_invite_stats")
    op.drop_table("telegram_chat_members")
    op.drop_table("telegram_invite_links")
    op.drop_table("telegram_users")
    op.drop_table("telegram_chats")

