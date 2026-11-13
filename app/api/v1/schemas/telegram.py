from datetime import datetime
from typing import Any

from pydantic import Field

from app.api.v1.schemas.common import APIModel


class TelegramUserPayload(APIModel):
    id: int
    is_bot: bool = False
    first_name: str
    last_name: str | None = None
    username: str | None = None


class TelegramChatPayload(APIModel):
    id: int
    title: str | None = None
    type: str  # private, group, supergroup, channel


class TelegramInviteLinkPayload(APIModel):
    invite_link: str
    creator: TelegramUserPayload | None = None
    name: str | None = None
    is_primary: bool = False
    is_revoked: bool = False


class TelegramChatMemberStatusPayload(APIModel):
    user: TelegramUserPayload
    status: str  # creator, administrator, member, restricted, left, kicked
    is_member: bool | None = None


class ChatMemberUpdatedPayload(APIModel):
    chat: TelegramChatPayload
    from_user: TelegramUserPayload = Field(..., alias="from")
    date: int
    old_chat_member: TelegramChatMemberStatusPayload
    new_chat_member: TelegramChatMemberStatusPayload
    invite_link: TelegramInviteLinkPayload | None = None
    via_chat_folder_invite_link: bool | None = None


class TelegramWebhookUpdate(APIModel):
    update_id: int
    chat_member: ChatMemberUpdatedPayload | None = None
    my_chat_member: ChatMemberUpdatedPayload | None = None

    # Allow extra fields for other Telegram update types without failing
    model_config = {
        "extra": "ignore",
        "populate_by_name": True,
        "from_attributes": True,
    }


class TelegramWebhookResponse(APIModel):
    ok: bool = True
    message: str | None = None


class TelegramInviteStatOut(APIModel):
    chat_id: int
    user_id: int
    total_invites: int
    updated_at: datetime


class TelegramLeaderboardEntry(APIModel):
    user_id: int
    username: str | None = None
    first_name: str
    total_invites: int


class TelegramWebhookRegistrationResponse(APIModel):
    ok: bool
    description: str | None = None
    url: str | None = None

