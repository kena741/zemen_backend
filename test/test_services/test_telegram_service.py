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


@pytest.mark.asyncio
async def test_private_dm_access_restricted_for_non_admin():
    from app.api.v1.schemas.telegram import TelegramMessagePayload

    update = TelegramWebhookUpdate(
        update_id=2001,
        message=TelegramMessagePayload(
            message_id=1,
            date=int(datetime.now(timezone.utc).timestamp()),
            chat=TelegramChatPayload(id=999, type="private"),
            from_user=TelegramUserPayload(id=999, first_name="RegularUser", is_bot=False),
            text="/start",
        ),
    )

    mock_db = MagicMock()
    mock_db.execute = AsyncMock()

    with patch(
        "app.core.services.telegram_service.get_admin_chats",
        new=AsyncMock(return_value=[]),
    ), patch(
        "app.core.services.telegram_service.send_message",
        new=AsyncMock(),
    ) as mock_send:
        res = await telegram_service.process_telegram_webhook_update(mock_db, update)
        assert res["handled"] is True
        assert res["is_admin"] is False
        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        assert "Access Restricted" in kwargs["text"]


@pytest.mark.asyncio
async def test_private_dm_access_granted_for_admin():
    from app.api.v1.schemas.telegram import TelegramMessagePayload
    from app.persistence.sqlalchemy.models.telegram import TelegramChat

    admin_chat = TelegramChat(
        chat_id=-1001234567890,
        title="Admin Supergroup",
        type="supergroup",
        is_active=True,
    )

    update = TelegramWebhookUpdate(
        update_id=2002,
        message=TelegramMessagePayload(
            message_id=2,
            date=int(datetime.now(timezone.utc).timestamp()),
            chat=TelegramChatPayload(id=111, type="private"),
            from_user=TelegramUserPayload(id=111, first_name="AdminUser", is_bot=False),
            text="/start",
        ),
    )

    mock_db = MagicMock()
    mock_db.execute = AsyncMock()

    with patch(
        "app.core.services.telegram_service.get_admin_chats",
        new=AsyncMock(return_value=[admin_chat]),
    ), patch(
        "app.core.services.telegram_service.send_message",
        new=AsyncMock(),
    ) as mock_send:
        res = await telegram_service.process_telegram_webhook_update(mock_db, update)
        assert res["handled"] is True
        assert res["is_admin"] is True
        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        assert "Admin Control Panel" in kwargs["text"]
        assert kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_group_message_directs_to_private_dm():
    from app.api.v1.schemas.telegram import TelegramMessagePayload

    update = TelegramWebhookUpdate(
        update_id=2003,
        message=TelegramMessagePayload(
            message_id=3,
            date=int(datetime.now(timezone.utc).timestamp()),
            chat=TelegramChatPayload(id=-1001234567890, title="Public Group", type="supergroup"),
            from_user=TelegramUserPayload(id=111, first_name="AdminUser", is_bot=False),
            text="/admin",
        ),
    )

    mock_db = MagicMock()
    mock_db.execute = AsyncMock()

    with patch(
        "app.core.services.telegram_service.send_message",
        new=AsyncMock(),
    ) as mock_send:
        res = await telegram_service.process_telegram_webhook_update(mock_db, update)
        assert res["handled"] is True
        assert res["type"] == "group_message"
        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        assert "Private Messages" in kwargs["text"]


@pytest.mark.asyncio
async def test_callback_query_chat_detail():
    from app.api.v1.schemas.telegram import CallbackQueryPayload, TelegramMessagePayload
    from app.api.v1.schemas.telegram import TelegramChatOut

    cb = CallbackQueryPayload(
        id="query_123",
        from_user=TelegramUserPayload(id=111, first_name="AdminUser", is_bot=False),
        message=TelegramMessagePayload(
            message_id=10,
            date=int(datetime.now(timezone.utc).timestamp()),
            chat=TelegramChatPayload(id=111, type="private"),
        ),
        data="chat:-1001234567890",
    )
    update = TelegramWebhookUpdate(update_id=3001, callback_query=cb)

    mock_db = MagicMock()
    mock_chat = TelegramChatOut(
        chat_id=-1001234567890,
        title="Admin Supergroup",
        type="supergroup",
        is_active=True,
        total_members=50,
        total_invites=25,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    with patch(
        "app.core.services.telegram_service.is_chat_admin",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.core.services.telegram_service.get_chat",
        new=AsyncMock(return_value=mock_chat),
    ), patch(
        "app.core.services.telegram_service.edit_message_text",
        new=AsyncMock(),
    ) as mock_edit, patch(
        "app.core.services.telegram_service.answer_callback_query",
        new=AsyncMock(),
    ) as mock_answer:
        res = await telegram_service.process_telegram_webhook_update(mock_db, update)
        assert res["handled"] is True
        assert res["action"] == "chat_detail"
        mock_edit.assert_called_once()
        mock_answer.assert_called_once()


@pytest.mark.asyncio
async def test_callback_query_export_csv():
    from app.api.v1.schemas.telegram import CallbackQueryPayload, TelegramMessagePayload

    cb = CallbackQueryPayload(
        id="query_124",
        from_user=TelegramUserPayload(id=111, first_name="AdminUser", is_bot=False),
        message=TelegramMessagePayload(
            message_id=11,
            date=int(datetime.now(timezone.utc).timestamp()),
            chat=TelegramChatPayload(id=111, type="private"),
        ),
        data="export:-1001234567890",
    )
    update = TelegramWebhookUpdate(update_id=3002, callback_query=cb)

    mock_db = MagicMock()

    with patch(
        "app.core.services.telegram_service.is_chat_admin",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.core.services.telegram_service.generate_chat_invites_csv",
        new=AsyncMock(return_value="Rank,Telegram User ID,Username,First Name,Last Name,Total Invites,Last Invite Timestamp (UTC)\n1,111,@top,Top,User,10,2026-11-13 10:00:00\n"),
    ), patch(
        "app.core.services.telegram_service.send_document",
        new=AsyncMock(),
    ) as mock_doc, patch(
        "app.core.services.telegram_service.answer_callback_query",
        new=AsyncMock(),
    ) as mock_answer:
        res = await telegram_service.process_telegram_webhook_update(mock_db, update)
        assert res["handled"] is True
        assert res["action"] == "export"
        mock_doc.assert_called_once()
        mock_answer.assert_called_once()


@pytest.mark.asyncio
async def test_private_message_register_group():
    from app.api.v1.schemas.telegram import TelegramMessagePayload
    from app.persistence.sqlalchemy.models.telegram import TelegramChat

    update = TelegramWebhookUpdate(
        update_id=2004,
        message=TelegramMessagePayload(
            message_id=4,
            date=int(datetime.now(timezone.utc).timestamp()),
            chat=TelegramChatPayload(id=111, type="private"),
            from_user=TelegramUserPayload(id=111, first_name="AdminUser", is_bot=False),
            text="/register -1002839533734",
        ),
    )

    mock_db = MagicMock()
    mock_db.execute = AsyncMock()

    registered_chat = TelegramChat(
        chat_id=-1002839533734,
        title="Zemen Service",
        type="supergroup",
        is_active=True,
    )

    with patch(
        "app.core.services.telegram_service.fetch_chat_info",
        new=AsyncMock(return_value={"id": -1002839533734, "title": "Zemen Service", "type": "supergroup"}),
    ), patch(
        "app.core.services.telegram_service.is_chat_admin",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.core.services.telegram_service.get_admin_chats",
        new=AsyncMock(return_value=[registered_chat]),
    ), patch(
        "app.core.services.telegram_service.send_message",
        new=AsyncMock(),
    ) as mock_send:
        res = await telegram_service.process_telegram_webhook_update(mock_db, update)
        assert res["handled"] is True
        assert res["action"] == "registered_group"
        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        assert "Group Connected Successfully" in kwargs["text"]
        assert "-1002839533734" in kwargs["text"]


@pytest.mark.asyncio
async def test_group_message_with_bot_mention():
    from app.api.v1.schemas.telegram import TelegramMessagePayload

    update = TelegramWebhookUpdate(
        update_id=2005,
        message=TelegramMessagePayload(
            message_id=5,
            date=int(datetime.now(timezone.utc).timestamp()),
            chat=TelegramChatPayload(id=-1002839533734, title="Zemen Group", type="supergroup"),
            from_user=TelegramUserPayload(id=111, first_name="AdminUser", is_bot=False),
            text="/id@ZemenInviteBot",
        ),
    )

    mock_db = MagicMock()
    mock_db.execute = AsyncMock()

    with patch(
        "app.core.services.telegram_service.send_message",
        new=AsyncMock(),
    ) as mock_send:
        res = await telegram_service.process_telegram_webhook_update(mock_db, update)
        assert res["handled"] is True
        assert res["type"] == "group_message"
        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        assert "-1002839533734" in kwargs["text"]
        assert "Tracked ✅" in kwargs["text"]



