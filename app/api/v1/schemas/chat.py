"""Pydantic schemas for Realtime Chat and Inboxes."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.base import MobileApiSchema


class ChatMessageOut(MobileApiSchema):
    chat_id: str = Field(serialization_alias="chatID")
    sender_id: str = Field(serialization_alias="senderId")
    receiver_id: str = Field(serialization_alias="receiverId")
    message: str | None = None
    media_url: str | None = Field(default=None, serialization_alias="mediaUrl")
    seen: bool = False
    type: str | None = "text"
    timestamp: datetime


class ChatInboxOut(MobileApiSchema):
    id: str
    sender_id: str = Field(serialization_alias="senderId")
    receiver_id: str = Field(serialization_alias="receiverId")
    last_message: str | None = Field(default=None, serialization_alias="lastMessage")
    media_url: str | None = Field(default=None, serialization_alias="mediaUrl")
    seen: bool = False
    type: str | None = "text"
    timestamp: datetime
    archive: bool = False
    peer_name: str | None = Field(default=None, serialization_alias="peerName")
    peer_image: str | None = Field(default=None, serialization_alias="peerImage")


class ChatMessageSend(MobileApiSchema):
    receiver_id: str = Field(alias="receiverId")
    message: str | None = None
    media_url: str | None = Field(default=None, alias="mediaUrl")
    type: str | None = "text"
    chat_id: str | None = Field(default=None, alias="chatID")


class MarkSeenBody(MobileApiSchema):
    peer_id: str = Field(alias="peerId")


class ChatSendBody(MobileApiSchema):
    message: str | None = None
    media_url: str | None = Field(default=None, alias="mediaUrl")
    type: str = "text"
    sender_id: str | None = Field(default=None, alias="senderId")
    chat_id: str | None = Field(default=None, alias="chatID")


class ChatBulkResult(MobileApiSchema):
    count: int

