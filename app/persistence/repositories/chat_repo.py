"""Repository for Realtime Chat messages and User Inboxes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.chat import ChatInboxDomain, ChatMessageDomain
from app.persistence.sqlalchemy.models.social import ChatInbox, ChatMessage


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def conversation_id(u1: str, u2: str) -> str:
        first, second = sorted([str(u1), str(u2)])
        return f"{first}_{second}"

    def to_message_domain(self, entity: ChatMessage) -> ChatMessageDomain:
        return ChatMessageDomain(
            chat_id=entity.chat_id,
            sender_id=entity.sender_id,
            receiver_id=entity.receiver_id,
            message=entity.message,
            media_url=entity.media_url,
            seen=bool(entity.seen),
            type=entity.type or "text",
            timestamp=entity.timestamp or datetime.now(timezone.utc),
            created_at=entity.created_at or datetime.now(timezone.utc),
        )

    def to_inbox_domain(self, entity: ChatInbox) -> ChatInboxDomain:
        return ChatInboxDomain(
            id=entity.id,
            sender_id=entity.sender_id,
            receiver_id=entity.receiver_id,
            last_message=entity.last_message,
            media_url=entity.media_url,
            seen=bool(entity.seen),
            type=entity.type or "text",
            timestamp=entity.timestamp or datetime.now(timezone.utc),
            archive=bool(entity.archive),
        )

    async def insert_message(
        self,
        sender_id: str,
        receiver_id: str,
        message: str | None = None,
        media_url: str | None = None,
        msg_type: str = "text",
        chat_id: str | None = None,
    ) -> ChatMessageDomain:
        now = datetime.now(timezone.utc)
        c_id = chat_id or str(uuid4())
        msg = ChatMessage(
            chat_id=c_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            message=message,
            media_url=media_url,
            seen=False,
            type=msg_type,
            timestamp=now,
            created_at=now,
            updated_at=now,
        )
        self.session.add(msg)

        # Upsert into chat_inbox
        conv_id = self.conversation_id(sender_id, receiver_id)
        stmt = select(ChatInbox).where(ChatInbox.id == conv_id)
        res = await self.session.execute(stmt)
        inbox = res.scalar_one_or_none()

        if inbox:
            inbox.last_message = message or ("[Media]" if media_url else "")
            inbox.media_url = media_url
            inbox.sender_id = sender_id
            inbox.receiver_id = receiver_id
            inbox.seen = False
            inbox.type = msg_type
            inbox.timestamp = now
            inbox.updated_at = now
        else:
            inbox = ChatInbox(
                id=conv_id,
                last_message=message or ("[Media]" if media_url else ""),
                media_url=media_url,
                sender_id=sender_id,
                receiver_id=receiver_id,
                seen=False,
                type=msg_type,
                timestamp=now,
                archive=False,
                created_at=now,
                updated_at=now,
            )
            self.session.add(inbox)

        await self.session.commit()
        await self.session.refresh(msg)
        return self.to_message_domain(msg)

    async def list_messages(
        self, user_id: str, peer_id: str, limit: int = 100, offset: int = 0
    ) -> list[ChatMessageDomain]:
        u1, u2 = str(user_id), str(peer_id)
        stmt = (
            select(ChatMessage)
            .where(
                or_(
                    (ChatMessage.sender_id == u1) & (ChatMessage.receiver_id == u2),
                    (ChatMessage.sender_id == u2) & (ChatMessage.receiver_id == u1),
                )
            )
            .order_by(ChatMessage.timestamp.asc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return [self.to_message_domain(m) for m in res.scalars().all()]

    async def list_inbox(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> list[ChatInboxDomain]:
        u_str = str(user_id)
        stmt = (
            select(ChatInbox)
            .where(
                or_(ChatInbox.sender_id == u_str, ChatInbox.receiver_id == u_str),
                ChatInbox.archive.is_(False),
            )
            .order_by(ChatInbox.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return [self.to_inbox_domain(ib) for ib in res.scalars().all()]

    async def mark_messages_seen(self, user_id: str, peer_id: str) -> None:
        u_str, p_str = str(user_id), str(peer_id)
        # 1. Update unread messages where receiver is user and sender is peer
        m_stmt = (
            update(ChatMessage)
            .where(ChatMessage.receiver_id == u_str, ChatMessage.sender_id == p_str, ChatMessage.seen.is_(False))
            .values(seen=True)
        )
        await self.session.execute(m_stmt)

        # 2. Update inbox if user was the receiver
        conv_id = self.conversation_id(u_str, p_str)
        ib_stmt = (
            update(ChatInbox)
            .where(ChatInbox.id == conv_id, ChatInbox.receiver_id == u_str)
            .values(seen=True)
        )
        await self.session.execute(ib_stmt)
        await self.session.commit()

    async def count_unread_messages(self, user_id: str) -> int:
        stmt = select(func.count(ChatMessage.chat_id)).where(
            ChatMessage.receiver_id == str(user_id),
            ChatMessage.seen.is_(False),
        )
        res = await self.session.execute(stmt)
        return int(res.scalar_one() or 0)

    async def delete_message(self, user_id: str, peer_id: str, chat_id: str) -> bool:
        u_str, p_str = str(user_id), str(peer_id)
        stmt = select(ChatMessage).where(ChatMessage.chat_id == chat_id)
        res = await self.session.execute(stmt)
        msg = res.scalar_one_or_none()
        if not msg:
            return False

        participants = {msg.sender_id, msg.receiver_id}
        if u_str not in participants:
            return False

        await self.session.delete(msg)
        await self.session.flush()

        # Sync inbox
        latest_stmt = (
            select(ChatMessage)
            .where(
                or_(
                    (ChatMessage.sender_id == u_str) & (ChatMessage.receiver_id == p_str),
                    (ChatMessage.sender_id == p_str) & (ChatMessage.receiver_id == u_str),
                )
            )
            .order_by(ChatMessage.timestamp.desc())
            .limit(1)
        )
        latest_res = await self.session.execute(latest_stmt)
        latest = latest_res.scalar_one_or_none()

        conv_id = self.conversation_id(u_str, p_str)
        inbox_stmt = select(ChatInbox).where(ChatInbox.id == conv_id)
        inbox_res = await self.session.execute(inbox_stmt)
        inbox = inbox_res.scalar_one_or_none()

        if latest and inbox:
            inbox.last_message = latest.message or ("[Media]" if latest.media_url else "")
            inbox.media_url = latest.media_url
            inbox.sender_id = latest.sender_id
            inbox.receiver_id = latest.receiver_id
            inbox.seen = latest.seen
            inbox.type = latest.type
            inbox.timestamp = latest.timestamp
        elif inbox:
            await self.session.delete(inbox)

        await self.session.commit()
        return True

    async def clear_conversation(self, user_id: str, peer_id: str) -> int:
        u_str, p_str = str(user_id), str(peer_id)
        stmt = select(ChatMessage).where(
            or_(
                (ChatMessage.sender_id == u_str) & (ChatMessage.receiver_id == p_str),
                (ChatMessage.sender_id == p_str) & (ChatMessage.receiver_id == u_str),
            )
        )
        res = await self.session.execute(stmt)
        msgs = list(res.scalars().all())
        count = len(msgs)
        for m in msgs:
            await self.session.delete(m)

        conv_id = self.conversation_id(u_str, p_str)
        inbox_stmt = select(ChatInbox).where(ChatInbox.id == conv_id)
        inbox_res = await self.session.execute(inbox_stmt)
        inbox = inbox_res.scalar_one_or_none()
        if inbox:
            await self.session.delete(inbox)

        await self.session.commit()
        return count
