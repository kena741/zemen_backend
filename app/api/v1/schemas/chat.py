from datetime import datetime

from pydantic import Field

from app.api.v1.schemas.common import APIModel


class ChatMessageOut(APIModel):
    chat_id: str = Field(serialization_alias="chatID")
    type: str | None = None
    sender_id: str = Field(serialization_alias="senderId")
    receiver_id: str = Field(serialization_alias="receiverId")
    message: str | None = None
    media_url: str | None = Field(default=None, serialization_alias="mediaUrl")
    seen: bool | None = None
    timestamp: datetime | None = None


class ChatInboxOut(APIModel):
    id: str
    last_message: str | None = Field(default=None, serialization_alias="lastMessage")
    media_url: str | None = Field(default=None, serialization_alias="mediaUrl")
    sender_id: str = Field(serialization_alias="senderId")
    receiver_id: str = Field(serialization_alias="receiverId")
    seen: bool | None = None
    type: str | None = None
    timestamp: datetime | None = None
    archive: bool | None = None


class ChatSendBody(APIModel):
    sender_id: str | None = Field(default=None, alias="senderId")
    message: str | None = None
    media_url: str | None = Field(default=None, alias="mediaUrl")
    type: str = "text"
    chat_id: str | None = Field(default=None, alias="chatID")


class ChatBulkResult(APIModel):
    count: int
