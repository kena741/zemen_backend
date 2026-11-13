from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.schemas.telegram import (
    ChatMemberUpdatedPayload,
    TelegramChatMemberStatusPayload,
    TelegramChatPayload,
    TelegramInviteLinkPayload,
    TelegramUserPayload,
    TelegramWebhookUpdate,
)
from app.core.services import telegram_service


@pytest.mark.asyncio
async def test_register_webhook_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "ok": True,
        "result": True,
        "description": "Webhook was set",
    }

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)) as mock_post:
        res = await telegram_service.register_webhook(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            webhook_url="https://api.example.com/api/v1/telegram/webhook",
            secret_token="custom_secret",
            allowed_updates=["chat_member", "my_chat_member"],
        )
        assert res.ok is True
        assert res.url == "https://api.example.com/api/v1/telegram/webhook"
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["allowed_updates"] == ["chat_member", "my_chat_member"]
        assert kwargs["json"]["secret_token"] == "custom_secret"


@pytest.mark.asyncio
async def test_register_webhook_missing_config(monkeypatch):
    monkeypatch.setattr(telegram_service.settings, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(telegram_service.settings, "TELEGRAM_WEBHOOK_URL", "")
    res = await telegram_service.register_webhook(
        bot_token="",
        webhook_url="",
    )
    assert res.ok is False
    assert "TELEGRAM_BOT_TOKEN is not configured" in (res.description or "")


@pytest.mark.asyncio
async def test_process_chat_member_updated_direct_add():
    """Tests that a direct add (User 111 adds User 222) credits User 111."""
    event = ChatMemberUpdatedPayload(
        chat=TelegramChatPayload(id=-1001234567890, title="Dev Group", type="supergroup"),
        from_user=TelegramUserPayload(id=111, first_name="Inviter", is_bot=False),
        date=int(datetime.now(timezone.utc).timestamp()),
        old_chat_member=TelegramChatMemberStatusPayload(
            user=TelegramUserPayload(id=222, first_name="Joiner", is_bot=False),
            status="left",
        ),
        new_chat_member=TelegramChatMemberStatusPayload(
            user=TelegramUserPayload(id=222, first_name="Joiner", is_bot=False),
            status="member",
        ),
    )

    mock_db = MagicMock()
    # Mocking execute: first select for existing_member returns None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.add = MagicMock()

    result = await telegram_service.process_chat_member_updated(mock_db, event)
    assert result["is_joining"] is True
    assert result["inviter_id"] == 111
    assert result["user_id"] == 222
    assert result["chat_id"] == -1001234567890
    assert result["incremented"] is True
    mock_db.add.assert_called_once()


@pytest.mark.asyncio
async def test_process_chat_member_updated_invite_link():
    """Tests that a user joining via link credits the link creator (User 333)."""
    event = ChatMemberUpdatedPayload(
        chat=TelegramChatPayload(id=-1001234567890, title="Dev Group", type="supergroup"),
        from_user=TelegramUserPayload(id=222, first_name="Joiner", is_bot=False),
        date=int(datetime.now(timezone.utc).timestamp()),
        old_chat_member=TelegramChatMemberStatusPayload(
            user=TelegramUserPayload(id=222, first_name="Joiner", is_bot=False),
            status="left",
        ),
        new_chat_member=TelegramChatMemberStatusPayload(
            user=TelegramUserPayload(id=222, first_name="Joiner", is_bot=False),
            status="member",
        ),
        invite_link=TelegramInviteLinkPayload(
            invite_link="https://t.me/+PromoLink123",
            creator=TelegramUserPayload(id=333, first_name="LinkCreator", is_bot=False),
            name="Promo Campaign",
        ),
    )

    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.add = MagicMock()

    result = await telegram_service.process_chat_member_updated(mock_db, event)
    assert result["is_joining"] is True
    assert result["inviter_id"] == 333
    assert result["incremented"] is True


@pytest.mark.asyncio
async def test_process_chat_member_rejoin_is_idempotent():
    """Tests that rejoining when already recorded does NOT increment the counter."""
    event = ChatMemberUpdatedPayload(
        chat=TelegramChatPayload(id=-1001234567890, title="Dev Group", type="supergroup"),
        from_user=TelegramUserPayload(id=111, first_name="Inviter", is_bot=False),
        date=int(datetime.now(timezone.utc).timestamp()),
        old_chat_member=TelegramChatMemberStatusPayload(
            user=TelegramUserPayload(id=222, first_name="Joiner", is_bot=False),
            status="left",
        ),
        new_chat_member=TelegramChatMemberStatusPayload(
            user=TelegramUserPayload(id=222, first_name="Joiner", is_bot=False),
            status="member",
        ),
    )

    mock_db = MagicMock()
    existing_member_mock = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_member_mock
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.add = MagicMock()

    result = await telegram_service.process_chat_member_updated(mock_db, event)
    assert result["is_joining"] is True
    # Crucial assertion: not incremented again!
    assert result["incremented"] is False
    mock_db.add.assert_not_called()
    assert existing_member_mock.status == "member"

