"""Service for Realtime Chat messaging, Inbox aggregation, and unread counters."""

from __future__ import annotations

from typing import Any

from app.domain.chat import ChatInboxDomain, ChatMessageDomain
from app.domain.exceptions import ValidationError
from app.persistence.repositories.chat_repo import ChatRepository


class ChatService:
    def __init__(self, chat_repo: ChatRepository) -> None:
        self.chat_repo = chat_repo

    async def send_message(
        self,
        sender_id: str,
        receiver_id: str,
        message: str | None = None,
        media_url: str | None = None,
        msg_type: str = "text",
        chat_id: str | None = None,
    ) -> ChatMessageDomain:
        if not message and not media_url:
            raise ValidationError("Message text or mediaUrl must be provided.")
        if str(sender_id) == str(receiver_id):
            raise ValidationError("Cannot send message to yourself.")

        return await self.chat_repo.insert_message(
            sender_id=str(sender_id),
            receiver_id=str(receiver_id),
            message=message,
            media_url=media_url,
            msg_type=msg_type,
            chat_id=chat_id,
        )

    async def list_conversation(
        self, user_id: str, peer_id: str, limit: int = 100, offset: int = 0
    ) -> list[ChatMessageDomain]:
        return await self.chat_repo.list_messages(
            user_id=str(user_id), peer_id=str(peer_id), limit=limit, offset=offset
        )

    async def list_inbox(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> list[ChatInboxDomain]:
        return await self.chat_repo.list_inbox(user_id=str(user_id), limit=limit, offset=offset)

    async def mark_seen(self, user_id: str, peer_id: str) -> None:
        await self.chat_repo.mark_messages_seen(user_id=str(user_id), peer_id=str(peer_id))

    async def get_unread_count(self, user_id: str) -> int:
        return await self.chat_repo.count_unread_messages(user_id=str(user_id))

    async def delete_message(self, user_id: str, peer_id: str, chat_id: str) -> bool:
        return await self.chat_repo.delete_message(user_id=str(user_id), peer_id=str(peer_id), chat_id=chat_id)

    async def clear_conversation(self, user_id: str, peer_id: str) -> int:
        return await self.chat_repo.clear_conversation(user_id=str(user_id), peer_id=str(peer_id))
