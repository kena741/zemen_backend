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
        assert mock_post.call_count == 2
        # First call is setWebhook
        first_call = mock_post.call_args_list[0]
        assert "setWebhook" in first_call[0][0]
        assert first_call[1]["json"]["allowed_updates"] == ["chat_member", "my_chat_member"]
        assert first_call[1]["json"]["secret_token"] == "custom_secret"
        # Second call is setMyCommands
        second_call = mock_post.call_args_list[1]
        assert "setMyCommands" in second_call[0][0]


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
    mock_db.execute = AsyncMock()
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
    mock_db.execute = AsyncMock()
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
    mock_db.execute = AsyncMock()
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
async def test_private_dm_not_in_group_prompts_to_join():
    from app.api.v1.schemas.telegram import TelegramMessagePayload
    from app.persistence.sqlalchemy.models.telegram import TelegramChat

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

    mock_chat = TelegramChat(
        chat_id=-1001234567890,
        title="Community Group",
        type="supergroup",
        is_active=True,
    )

    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_chat]
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch(
        "app.core.services.telegram_service.get_admin_chats",
        new=AsyncMock(return_value=[]),
    ), patch(
        "app.core.services.telegram_service.is_chat_member_or_admin",
        new=AsyncMock(return_value=False),
    ), patch(
        "app.core.services.telegram_service.fetch_chat_info",
        new=AsyncMock(return_value={"id": -1001234567890, "title": "Community Group", "username": "community_grp"}),
    ), patch(
        "app.core.services.telegram_service.send_message",
        new=AsyncMock(),
    ) as mock_send:
        res = await telegram_service.process_telegram_webhook_update(mock_db, update)
        assert res["handled"] is True
        assert res["action"] == "not_member_prompt"
        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        assert "Welcome, RegularUser" in kwargs["text"]
        assert "Community Group" in kwargs["text"]
        assert kwargs["reply_markup"] is not None


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
    mock_db.execute = AsyncMock()
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
    mock_db.execute = AsyncMock()

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


@pytest.mark.asyncio
async def test_member_receives_personal_invite_card():
    """Tests that an active group member sending /invite receives their personal invite link & stats."""
    from app.api.v1.schemas.telegram import TelegramMessagePayload
    from app.persistence.sqlalchemy.models.telegram import TelegramChat

    update = TelegramWebhookUpdate(
        update_id=2006,
        message=TelegramMessagePayload(
            message_id=6,
            date=int(datetime.now(timezone.utc).timestamp()),
            chat=TelegramChatPayload(id=777, type="private"),
            from_user=TelegramUserPayload(id=777, first_name="Abebe", is_bot=False),
            text="/invite",
        ),
    )

    mock_chat = TelegramChat(
        chat_id=-1002839533734,
        title="Zemen Service",
        type="supergroup",
        is_active=True,
    )

    mock_db = MagicMock()
    mock_db.execute = AsyncMock()

    with patch(
        "app.core.services.telegram_service.get_admin_chats",
        new=AsyncMock(return_value=[]),
    ), patch(
        "app.persistence.repositories.telegram_repo.TelegramRepository.get_active_group_chats",
        new=AsyncMock(return_value=[mock_chat]),
    ), patch(
        "app.core.services.telegram_service.is_chat_member_or_admin",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.core.services.telegram_service.get_or_create_user_invite_link",
        new=AsyncMock(return_value="https://t.me/+AbebeUniqueLink"),
    ), patch(
        "app.persistence.repositories.telegram_repo.TelegramRepository.get_user_invite_stat",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.persistence.repositories.telegram_repo.TelegramRepository.get_user_rank",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.core.services.telegram_service.send_message",
        new=AsyncMock(),
    ) as mock_send:
        res = await telegram_service.process_telegram_webhook_update(mock_db, update)
        assert res["handled"] is True
        assert res["action"] == "user_invite_card"
        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        assert "Your Personal Invite Link" in kwargs["text"]
        assert "https://t.me/+AbebeUniqueLink" in kwargs["text"]
        assert kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_member_deep_link_generates_invite_card():
    """Tests opening /start invite_1002839533734 generates personal invite link."""
    from app.api.v1.schemas.telegram import TelegramMessagePayload
    from app.persistence.sqlalchemy.models.telegram import TelegramChat

    update = TelegramWebhookUpdate(
        update_id=2007,
        message=TelegramMessagePayload(
            message_id=7,
            date=int(datetime.now(timezone.utc).timestamp()),
            chat=TelegramChatPayload(id=777, type="private"),
            from_user=TelegramUserPayload(id=777, first_name="Abebe", is_bot=False),
            text="/start invite_1002839533734",
        ),
    )

    mock_chat = TelegramChat(
        chat_id=-1002839533734,
        title="Zemen Service",
        type="supergroup",
        is_active=True,
    )

    mock_db = MagicMock()
    mock_db.execute = AsyncMock()

    with patch(
        "app.persistence.repositories.telegram_repo.TelegramRepository.get_chat",
        new=AsyncMock(return_value=mock_chat),
    ), patch(
        "app.core.services.telegram_service.is_chat_member_or_admin",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.core.services.telegram_service.get_or_create_user_invite_link",
        new=AsyncMock(return_value="https://t.me/+DeepLinkAbebe"),
    ), patch(
        "app.persistence.repositories.telegram_repo.TelegramRepository.get_user_invite_stat",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.persistence.repositories.telegram_repo.TelegramRepository.get_user_rank",
        new=AsyncMock(return_value=5),
    ), patch(
        "app.core.services.telegram_service.is_chat_admin",
        new=AsyncMock(return_value=False),
    ), patch(
        "app.core.services.telegram_service.send_message",
        new=AsyncMock(),
    ) as mock_send:
        res = await telegram_service.process_telegram_webhook_update(mock_db, update)
        assert res["handled"] is True
        assert res["action"] == "deep_link_invite"
        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        assert "https://t.me/+DeepLinkAbebe" in kwargs["text"]
        assert "#5" in kwargs["text"]


@pytest.mark.asyncio
async def test_process_chat_member_updated_bot_created_link_attributed_to_member():
    """
    Tests that when a join occurs via a link created by the bot (creator.is_bot=True),
    the join is correctly attributed to the human member who requested the link.
    """
    from app.persistence.sqlalchemy.models.telegram import TelegramInviteLink

    event = ChatMemberUpdatedPayload(
        chat=TelegramChatPayload(id=-1002839533734, title="Zemen Service", type="supergroup"),
        from_user=TelegramUserPayload(id=888, first_name="NewJoiner", is_bot=False),
        date=int(datetime.now(timezone.utc).timestamp()),
        old_chat_member=TelegramChatMemberStatusPayload(
            user=TelegramUserPayload(id=888, first_name="NewJoiner", is_bot=False),
            status="left",
        ),
        new_chat_member=TelegramChatMemberStatusPayload(
            user=TelegramUserPayload(id=888, first_name="NewJoiner", is_bot=False),
            status="member",
        ),
        invite_link=TelegramInviteLinkPayload(
            invite_link="https://t.me/+MemberTrackedLink",
            creator=TelegramUserPayload(id=9103729346, first_name="Zemen Bot", is_bot=True),
            name="Abebe (777)",
        ),
    )

    db_link = TelegramInviteLink(
        invite_link="https://t.me/+MemberTrackedLink",
        chat_id=-1002839533734,
        creator_user_id=777,  # Human member Abebe
        name="Abebe (777)",
        is_primary=False,
        usage_count=0,
    )

    mock_db = MagicMock()
    mock_db.execute = AsyncMock()

    with patch(
        "app.persistence.repositories.telegram_repo.TelegramRepository.get_invite_link",
        new=AsyncMock(return_value=db_link),
    ), patch(
        "app.persistence.repositories.telegram_repo.TelegramRepository.upsert_chat",
        new=AsyncMock(),
    ), patch(
        "app.persistence.repositories.telegram_repo.TelegramRepository.upsert_user",
        new=AsyncMock(),
    ), patch(
        "app.persistence.repositories.telegram_repo.TelegramRepository.upsert_invite_link",
        new=AsyncMock(),
    ), patch(
        "app.persistence.repositories.telegram_repo.TelegramRepository.get_chat_member",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.persistence.repositories.telegram_repo.TelegramRepository.record_member_join",
        new=AsyncMock(),
    ) as mock_record, patch(
        "app.persistence.repositories.telegram_repo.TelegramRepository.increment_user_invites",
        new=AsyncMock(),
    ) as mock_inc_user, patch(
        "app.persistence.repositories.telegram_repo.TelegramRepository.increment_link_usage",
        new=AsyncMock(),
    ) as mock_inc_link:
        result = await telegram_service.process_chat_member_updated(mock_db, event)
        assert result["is_joining"] is True
        assert result["inviter_id"] == 777  # Crucial assertion: credited to Abebe, NOT the bot!
        assert result["incremented"] is True

        mock_record.assert_called_once_with(
            chat_id=-1002839533734,
            user_id=888,
            inviter_user_id=777,
            invite_link="https://t.me/+MemberTrackedLink",
            status="member",
            joined_at=mock_record.call_args[1]["joined_at"],
        )
        mock_inc_user.assert_called_once_with(
            chat_id=-1002839533734,
            user_id=777,
        )
        mock_inc_link.assert_called_once_with(
            invite_link="https://t.me/+MemberTrackedLink",
        )


@pytest.mark.asyncio
async def test_callback_query_user_link_and_leaderboard():
    """Tests member callback queries for viewing invite link and public leaderboard."""
    from app.api.v1.schemas.telegram import CallbackQueryPayload, TelegramMessagePayload
    from app.persistence.sqlalchemy.models.telegram import TelegramChat

    cb_link = CallbackQueryPayload(
        id="q_link_1",
        from_user=TelegramUserPayload(id=777, first_name="Abebe", is_bot=False),
        message=TelegramMessagePayload(
            message_id=20,
            date=int(datetime.now(timezone.utc).timestamp()),
            chat=TelegramChatPayload(id=777, type="private"),
        ),
        data="user_link:-1002839533734",
    )
    update = TelegramWebhookUpdate(update_id=4001, callback_query=cb_link)

    mock_chat = TelegramChat(chat_id=-1002839533734, title="Zemen Service", type="supergroup", is_active=True)
    mock_db = MagicMock()
    mock_db.execute = AsyncMock()

    with patch(
        "app.core.services.telegram_service.is_chat_member_or_admin",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.persistence.repositories.telegram_repo.TelegramRepository.get_chat",
        new=AsyncMock(return_value=mock_chat),
    ), patch(
        "app.core.services.telegram_service.get_or_create_user_invite_link",
        new=AsyncMock(return_value="https://t.me/+AbebeUnique"),
    ), patch(
        "app.persistence.repositories.telegram_repo.TelegramRepository.get_user_invite_stat",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.persistence.repositories.telegram_repo.TelegramRepository.get_user_rank",
        new=AsyncMock(return_value=1),
    ), patch(
        "app.core.services.telegram_service.is_chat_admin",
        new=AsyncMock(return_value=False),
    ), patch(
        "app.core.services.telegram_service.edit_message_text",
        new=AsyncMock(),
    ) as mock_edit, patch(
        "app.core.services.telegram_service.answer_callback_query",
        new=AsyncMock(),
    ) as mock_answer:
        res = await telegram_service.process_telegram_webhook_update(mock_db, update)
        assert res["handled"] is True
        assert res["action"] == "user_link"
        mock_edit.assert_called_once()
        mock_answer.assert_called_once()


@pytest.mark.asyncio
async def test_group_message_invite_command_sends_deep_link():
    """Tests that typing /invite in a group sends a prompt with a direct button to bot DM."""
    from app.api.v1.schemas.telegram import TelegramMessagePayload

    update = TelegramWebhookUpdate(
        update_id=2008,
        message=TelegramMessagePayload(
            message_id=8,
            date=int(datetime.now(timezone.utc).timestamp()),
            chat=TelegramChatPayload(id=-1002839533734, title="Zemen Service", type="supergroup"),
            from_user=TelegramUserPayload(id=777, first_name="Abebe", is_bot=False),
            text="/invite",
        ),
    )

    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.execute = AsyncMock()

    with patch(
        "app.core.services.telegram_service.get_bot_username",
        new=AsyncMock(return_value="zemen_service_bot"),
    ), patch(
        "app.core.services.telegram_service.send_message",
        new=AsyncMock(),
    ) as mock_send:
        res = await telegram_service.process_telegram_webhook_update(mock_db, update)
        assert res["handled"] is True
        assert res["type"] == "group_message"
        assert res["action"] == "invite_link_prompt"
        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        assert "Get Your Personal Invite Link" in kwargs["text"] or "personal invite link" in kwargs["text"]
        buttons = kwargs["reply_markup"]["inline_keyboard"]
        assert "t.me/zemen_service_bot?start=invite_1002839533734" in buttons[0][0]["url"]



