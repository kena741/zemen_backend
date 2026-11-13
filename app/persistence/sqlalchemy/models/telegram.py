from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.sqlalchemy.base import Base


class TelegramChat(Base):
    """Stores Telegram groups, supergroups, and channels where the bot operates."""

    __tablename__ = "telegram_chats"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)  # group, supergroup, channel
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    members: Mapped[list["TelegramChatMember"]] = relationship(
        "TelegramChatMember", back_populates="chat", cascade="all, delete-orphan"
    )
    invite_links: Mapped[list["TelegramInviteLink"]] = relationship(
        "TelegramInviteLink", back_populates="chat", cascade="all, delete-orphan"
    )
    invite_stats: Mapped[list["TelegramInviteStat"]] = relationship(
        "TelegramInviteStat", back_populates="chat", cascade="all, delete-orphan"
    )


class TelegramUser(Base):
    """Stores Telegram users encountered via membership and invite events."""

    __tablename__ = "telegram_users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    last_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    created_invite_links: Mapped[list["TelegramInviteLink"]] = relationship(
        "TelegramInviteLink", back_populates="creator"
    )


class TelegramInviteLink(Base):
    """Stores trackable Telegram invite links created by users or the bot."""

    __tablename__ = "telegram_invite_links"

    invite_link: Mapped[str] = mapped_column(Text, primary_key=True)
    chat_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("telegram_chats.chat_id", ondelete="CASCADE"), index=True, nullable=False
    )
    creator_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("telegram_users.user_id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chat: Mapped["TelegramChat"] = relationship("TelegramChat", back_populates="invite_links")
    creator: Mapped["TelegramUser | None"] = relationship(
        "TelegramUser", back_populates="created_invite_links"
    )


class TelegramChatMember(Base):
    """Membership record for each user in a chat to track join source and prevent duplicate counts."""

    __tablename__ = "telegram_chat_members"
    __table_args__ = (
        UniqueConstraint("chat_id", "user_id", name="uq_telegram_chat_members_chat_user"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    chat_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("telegram_chats.chat_id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("telegram_users.user_id", ondelete="CASCADE"), index=True, nullable=False
    )
    inviter_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("telegram_users.user_id", ondelete="SET NULL"), nullable=True, index=True
    )
    invite_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)  # member, administrator, left, kicked, restricted
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    chat: Mapped["TelegramChat"] = relationship("TelegramChat", back_populates="members")
    user: Mapped["TelegramUser"] = relationship("TelegramUser", foreign_keys=[user_id])
    inviter: Mapped["TelegramUser | None"] = relationship("TelegramUser", foreign_keys=[inviter_user_id])


class TelegramInviteStat(Base):
    """Aggregated invite counters per user per chat."""

    __tablename__ = "telegram_invite_stats"

    chat_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("telegram_chats.chat_id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("telegram_users.user_id", ondelete="CASCADE"), primary_key=True
    )
    total_invites: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    chat: Mapped["TelegramChat"] = relationship("TelegramChat", back_populates="invite_stats")
    user: Mapped["TelegramUser"] = relationship("TelegramUser", foreign_keys=[user_id])

