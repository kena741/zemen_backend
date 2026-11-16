"""Repository for Telegram chat, user, invite link, and membership persistence."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.telegram import (
    TelegramChatDomain,
    TelegramInviteStatDomain,
    TelegramLeaderboardDomain,
)
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.telegram import (
    TelegramChat,
    TelegramChatMember,
    TelegramInviteLink,
    TelegramInviteStat,
    TelegramUser,
)


class TelegramRepository(BaseRepository[TelegramChat, Any]):
    """SQLAlchemy repository for Telegram bot invite tracking and administration."""

    model = TelegramChat

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def _flush(self) -> None:
        """Flushes session changes safely supporting mock or async sessions."""
        if hasattr(self.session, "flush"):
            res = self.session.flush()
            if asyncio.iscoroutine(res):
                await res

    # =========================================================================
    # Chat Persistence
    # =========================================================================

    async def upsert_chat(
        self,
        chat_id: int,
        title: str | None,
        type: str,
        is_active: bool = True,
    ) -> None:
        """Upserts a group, supergroup, or channel record."""
        stmt = (
            insert(TelegramChat)
            .values(
                chat_id=chat_id,
                title=title,
                type=type,
                is_active=is_active,
            )
            .on_conflict_do_update(
                index_elements=[TelegramChat.chat_id],
                set_={
                    "title": title,
                    "type": type,
                    "is_active": is_active,
                    "updated_at": func.now(),
                },
            )
        )
        await self.session.execute(stmt)
        await self._flush()

    async def get_chat(self, chat_id: int) -> TelegramChat | None:
        """Retrieves raw TelegramChat entity by chat_id."""
        stmt = select(TelegramChat).where(TelegramChat.chat_id == chat_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_active_group_chats(self) -> list[TelegramChat]:
        """Returns all active groups, supergroups, and channels for admin authorization checks."""
        stmt = select(TelegramChat).where(
            TelegramChat.is_active == True,  # noqa: E712
            TelegramChat.type.in_(["group", "supergroup", "channel"]),
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def list_chats_with_counts(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TelegramChatDomain]:
        """Lists tracked chats with aggregated active member counts and verified invite counts."""
        member_count_subq = (
            select(
                TelegramChatMember.chat_id,
                func.count(TelegramChatMember.id).label("total_members"),
            )
            .where(TelegramChatMember.status.in_(["member", "administrator"]))
            .group_by(TelegramChatMember.chat_id)
            .subquery()
        )

        invite_count_subq = (
            select(
                TelegramInviteStat.chat_id,
                func.coalesce(func.sum(TelegramInviteStat.total_invites), 0).label("total_invites"),
            )
            .group_by(TelegramInviteStat.chat_id)
            .subquery()
        )

        stmt = (
            select(
                TelegramChat,
                func.coalesce(member_count_subq.c.total_members, 0).label("total_members"),
                func.coalesce(invite_count_subq.c.total_invites, 0).label("total_invites"),
            )
            .outerjoin(member_count_subq, TelegramChat.chat_id == member_count_subq.c.chat_id)
            .outerjoin(invite_count_subq, TelegramChat.chat_id == invite_count_subq.c.chat_id)
            .where(TelegramChat.type.in_(["group", "supergroup", "channel"]))
            .order_by(TelegramChat.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        rows = res.all()

        return [
            TelegramChatDomain(
                chat_id=chat.chat_id,
                title=chat.title,
                type=chat.type,
                is_active=chat.is_active,
                total_members=total_members,
                total_invites=total_invites,
                created_at=chat.created_at,
                updated_at=chat.updated_at,
            )
            for chat, total_members, total_invites in rows
        ]

    async def get_chat_with_counts(self, chat_id: int) -> TelegramChatDomain | None:
        """Retrieves a single tracked chat with aggregated member and invite counts."""
        member_count_subq = (
            select(
                func.count(TelegramChatMember.id).label("total_members"),
            )
            .where(
                TelegramChatMember.chat_id == chat_id,
                TelegramChatMember.status.in_(["member", "administrator"]),
            )
            .scalar_subquery()
        )

        invite_count_subq = (
            select(
                func.coalesce(func.sum(TelegramInviteStat.total_invites), 0).label("total_invites"),
            )
            .where(TelegramInviteStat.chat_id == chat_id)
            .scalar_subquery()
        )

        stmt = select(
            TelegramChat,
            func.coalesce(member_count_subq, 0).label("total_members"),
            func.coalesce(invite_count_subq, 0).label("total_invites"),
        ).where(TelegramChat.chat_id == chat_id)

        res = await self.session.execute(stmt)
        row = res.first()
        if not row:
            return None

        chat, total_members, total_invites = row
        return TelegramChatDomain(
            chat_id=chat.chat_id,
            title=chat.title,
            type=chat.type,
            is_active=chat.is_active,
            total_members=total_members,
            total_invites=total_invites,
            created_at=chat.created_at,
            updated_at=chat.updated_at,
        )

    # =========================================================================
    # User Persistence
    # =========================================================================

    async def upsert_user(
        self,
        user_id: int,
        username: str | None,
        first_name: str,
        last_name: str | None = None,
        is_bot: bool = False,
    ) -> None:
        """Upserts a Telegram user record."""
        stmt = (
            insert(TelegramUser)
            .values(
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                is_bot=is_bot,
            )
            .on_conflict_do_update(
                index_elements=[TelegramUser.user_id],
                set_={
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "is_bot": is_bot,
                    "updated_at": func.now(),
                },
            )
        )
        await self.session.execute(stmt)
        await self._flush()

    async def get_user(self, user_id: int) -> TelegramUser | None:
        """Retrieves user entity by user_id."""
        stmt = select(TelegramUser).where(TelegramUser.user_id == user_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    # =========================================================================
    # Invite Link Persistence
    # =========================================================================

    async def get_invite_link(self, invite_link: str) -> TelegramInviteLink | None:
        """Retrieves raw TelegramInviteLink entity by invite_link URL."""
        stmt = select(TelegramInviteLink).where(TelegramInviteLink.invite_link == invite_link)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_user_invite_link(self, chat_id: int, user_id: int) -> TelegramInviteLink | None:
        """Retrieves existing trackable personal invite link created for a user in a specific chat."""
        stmt = (
            select(TelegramInviteLink)
            .where(
                TelegramInviteLink.chat_id == chat_id,
                TelegramInviteLink.creator_user_id == user_id,
                TelegramInviteLink.is_primary == False,  # noqa: E712
            )
            .order_by(TelegramInviteLink.created_at.desc())
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def upsert_invite_link(
        self,
        invite_link: str,
        chat_id: int,
        creator_user_id: int | None = None,
        name: str | None = None,
        is_primary: bool = False,
    ) -> None:
        """Upserts an invite link metadata record while preserving existing creator attribution."""
        existing = await self.get_invite_link(invite_link)
        effective_creator_id = creator_user_id
        effective_name = name
        if existing:
            if effective_creator_id is None and existing.creator_user_id is not None:
                effective_creator_id = existing.creator_user_id
            if effective_name is None and existing.name is not None:
                effective_name = existing.name

        stmt = (
            insert(TelegramInviteLink)
            .values(
                invite_link=invite_link,
                chat_id=chat_id,
                creator_user_id=effective_creator_id,
                name=effective_name,
                is_primary=is_primary,
            )
            .on_conflict_do_update(
                index_elements=[TelegramInviteLink.invite_link],
                set_={
                    "creator_user_id": effective_creator_id,
                    "name": effective_name,
                    "is_primary": is_primary,
                },
            )
        )
        await self.session.execute(stmt)
        await self._flush()

    async def increment_link_usage(self, invite_link: str) -> None:
        """Increments the verified join count for an invite link."""
        stmt = (
            update(TelegramInviteLink)
            .where(TelegramInviteLink.invite_link == invite_link)
            .values(usage_count=TelegramInviteLink.usage_count + 1)
        )
        await self.session.execute(stmt)
        await self._flush()

    async def list_top_invite_links(self, chat_id: int, limit: int = 10) -> list[TelegramInviteLink]:
        """Lists the top performing invite links for a chat sorted by verified joins."""
        stmt = (
            select(TelegramInviteLink)
            .where(TelegramInviteLink.chat_id == chat_id)
            .order_by(TelegramInviteLink.usage_count.desc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # =========================================================================
    # Member & Invite Stats Persistence
    # =========================================================================

    async def get_chat_member(self, chat_id: int, user_id: int) -> TelegramChatMember | None:
        """Fetches existing membership record for idempotency checks."""
        stmt = select(TelegramChatMember).where(
            TelegramChatMember.chat_id == chat_id,
            TelegramChatMember.user_id == user_id,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def record_member_join(
        self,
        chat_id: int,
        user_id: int,
        inviter_user_id: int | None,
        invite_link: str | None,
        status: str,
        joined_at: datetime | None = None,
    ) -> TelegramChatMember:
        """Records a new member join with inviter attribution."""
        member = TelegramChatMember(
            chat_id=chat_id,
            user_id=user_id,
            inviter_user_id=inviter_user_id,
            invite_link=invite_link,
            status=status,
            joined_at=joined_at or datetime.now(timezone.utc),
        )
        self.session.add(member)
        await self._flush()
        return member

    async def update_member_status(self, chat_id: int, user_id: int, status: str) -> None:
        """Updates membership status without altering inviter attribution (e.g. on leave or rejoin)."""
        stmt = (
            update(TelegramChatMember)
            .where(
                TelegramChatMember.chat_id == chat_id,
                TelegramChatMember.user_id == user_id,
            )
            .values(
                status=status,
                updated_at=func.now(),
            )
        )
        await self.session.execute(stmt)
        await self._flush()

    async def increment_user_invites(self, chat_id: int, user_id: int) -> None:
        """
        Atomically increments the verified invite count for a user in a chat.
        """
        stmt = (
            insert(TelegramInviteStat)
            .values(
                chat_id=chat_id,
                user_id=user_id,
                total_invites=1,
            )
            .on_conflict_do_update(
                index_elements=[TelegramInviteStat.chat_id, TelegramInviteStat.user_id],
                set_={
                    "total_invites": TelegramInviteStat.total_invites + 1,
                    "updated_at": func.now(),
                },
            )
        )
        await self.session.execute(stmt)
        await self._flush()

    async def get_leaderboard(self, chat_id: int, limit: int = 20) -> list[TelegramLeaderboardDomain]:
        """Retrieves top inviters ranked by verified joins."""
        stmt = (
            select(
                TelegramInviteStat.user_id,
                TelegramUser.username,
                TelegramUser.first_name,
                TelegramInviteStat.total_invites,
            )
            .join(TelegramUser, TelegramUser.user_id == TelegramInviteStat.user_id)
            .where(TelegramInviteStat.chat_id == chat_id)
            .order_by(TelegramInviteStat.total_invites.desc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        rows = res.all()
        return [
            TelegramLeaderboardDomain(
                user_id=row.user_id,
                username=row.username,
                first_name=row.first_name,
                total_invites=row.total_invites,
            )
            for row in rows
        ]

    async def get_user_invite_stat(self, chat_id: int, user_id: int) -> TelegramInviteStat | None:
        """Retrieves invite stat record for a specific user in a chat."""
        stmt = select(TelegramInviteStat).where(
            TelegramInviteStat.chat_id == chat_id,
            TelegramInviteStat.user_id == user_id,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_user_rank(self, chat_id: int, user_id: int) -> int | None:
        """Calculates rank of user in a chat based on total verified invites."""
        stat = await self.get_user_invite_stat(chat_id, user_id)
        if not stat or stat.total_invites <= 0:
            return None
        stmt = select(func.count(TelegramInviteStat.user_id)).where(
            TelegramInviteStat.chat_id == chat_id,
            TelegramInviteStat.total_invites > stat.total_invites,
        )
        res = await self.session.execute(stmt)
        higher_count = res.scalar_one_or_none() or 0
        return higher_count + 1

    async def get_user_member_chats(self, user_id: int) -> list[TelegramChat]:
        """Finds all active chats where the user is an active member or administrator according to DB."""
        stmt = (
            select(TelegramChat)
            .join(TelegramChatMember, TelegramChatMember.chat_id == TelegramChat.chat_id)
            .where(
                TelegramChatMember.user_id == user_id,
                TelegramChatMember.status.in_(["member", "administrator"]),
                TelegramChat.is_active == True,  # noqa: E712
            )
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_chat_invites_for_csv(self, chat_id: int) -> list[Any]:
        """Fetches full ranking and user metadata for CSV export."""
        stmt = (
            select(
                TelegramInviteStat.user_id,
                TelegramUser.username,
                TelegramUser.first_name,
                TelegramUser.last_name,
                TelegramInviteStat.total_invites,
                TelegramInviteStat.updated_at,
            )
            .join(TelegramUser, TelegramUser.user_id == TelegramInviteStat.user_id)
            .where(TelegramInviteStat.chat_id == chat_id)
            .order_by(TelegramInviteStat.total_invites.desc())
        )
        res = await self.session.execute(stmt)
        return list(res.all())
