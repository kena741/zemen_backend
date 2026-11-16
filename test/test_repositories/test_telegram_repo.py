"""Unit tests for TelegramRepository persistence methods."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.persistence.repositories.telegram_repo import TelegramRepository
from app.persistence.sqlalchemy.models.telegram import (
    TelegramChat,
    TelegramChatMember,
    TelegramInviteLink,
    TelegramInviteStat,
    TelegramUser,
)


@pytest.mark.asyncio
async def test_telegram_repo_chat_operations():
    mock_session = MagicMock()
    mock_session.flush = AsyncMock()

    now = datetime.now(timezone.utc)
    chat = TelegramChat(
        chat_id=-1001234567890,
        title="Test Group",
        type="supergroup",
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    mock_result = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    repo = TelegramRepository(mock_session)

    # 1. upsert_chat
    await repo.upsert_chat(chat_id=-1001234567890, title="Test Group", type="supergroup")
    mock_session.execute.assert_called()
    mock_session.flush.assert_called()

    # 2. get_chat
    mock_result.scalar_one_or_none.return_value = chat
    found_chat = await repo.get_chat(-1001234567890)
    assert found_chat is not None
    assert found_chat.chat_id == -1001234567890

    # 3. get_active_group_chats
    mock_result.scalars.return_value.all.return_value = [chat]
    active_chats = await repo.get_active_group_chats()
    assert len(active_chats) == 1
    assert active_chats[0].chat_id == -1001234567890

    # 4. list_chats_with_counts
    mock_result.all.return_value = [(chat, 15, 8)]
    listed = await repo.list_chats_with_counts(limit=10, offset=0)
    assert len(listed) == 1
    assert listed[0].total_members == 15
    assert listed[0].total_invites == 8

    # 5. get_chat_with_counts
    mock_result.first.return_value = (chat, 15, 8)
    chat_with_counts = await repo.get_chat_with_counts(-1001234567890)
    assert chat_with_counts is not None
    assert chat_with_counts.total_members == 15
    assert chat_with_counts.total_invites == 8


@pytest.mark.asyncio
async def test_telegram_repo_user_operations():
    mock_session = MagicMock()
    mock_session.flush = AsyncMock()

    user = TelegramUser(
        user_id=111,
        username="test_user",
        first_name="Test",
        last_name="User",
        is_bot=False,
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_session.execute = AsyncMock(return_value=mock_result)

    repo = TelegramRepository(mock_session)
    await repo.upsert_user(
        user_id=111,
        username="test_user",
        first_name="Test",
        last_name="User",
        is_bot=False,
    )
    mock_session.execute.assert_called()

    found_user = await repo.get_user(111)
    assert found_user is not None
    assert found_user.user_id == 111


@pytest.mark.asyncio
async def test_telegram_repo_invite_link_operations():
    mock_session = MagicMock()
    mock_session.flush = AsyncMock()

    link = TelegramInviteLink(
        invite_link="https://t.me/+AbCdEf",
        chat_id=-1001234567890,
        creator_user_id=111,
        name="Campaign A",
        is_primary=True,
        usage_count=5,
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [link]
    mock_session.execute = AsyncMock(return_value=mock_result)

    repo = TelegramRepository(mock_session)
    await repo.upsert_invite_link(
        invite_link="https://t.me/+AbCdEf",
        chat_id=-1001234567890,
        creator_user_id=111,
        name="Campaign A",
        is_primary=True,
    )
    mock_session.execute.assert_called()

    await repo.increment_link_usage("https://t.me/+AbCdEf")
    mock_session.flush.assert_called()

    top_links = await repo.list_top_invite_links(chat_id=-1001234567890, limit=5)
    assert len(top_links) == 1
    assert top_links[0].usage_count == 5


@pytest.mark.asyncio
async def test_telegram_repo_membership_and_invite_stats():
    mock_session = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.add = MagicMock()

    now = datetime.now(timezone.utc)
    member = TelegramChatMember(
        id=uuid4(),
        chat_id=-1001234567890,
        user_id=222,
        inviter_user_id=111,
        invite_link="https://t.me/+AbCdEf",
        status="member",
        joined_at=now,
    )

    stat = TelegramInviteStat(
        chat_id=-1001234567890,
        user_id=111,
        total_invites=10,
        updated_at=now,
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = member
    mock_session.execute = AsyncMock(return_value=mock_result)

    repo = TelegramRepository(mock_session)

    # get_chat_member
    found_member = await repo.get_chat_member(-1001234567890, 222)
    assert found_member is not None
    assert found_member.user_id == 222

    # record_member_join
    new_mem = await repo.record_member_join(
        chat_id=-1001234567890,
        user_id=333,
        inviter_user_id=111,
        invite_link=None,
        status="member",
    )
    assert new_mem.user_id == 333
    mock_session.add.assert_called_once()

    # update_member_status
    await repo.update_member_status(-1001234567890, 222, "left")
    mock_session.execute.assert_called()

    # increment_user_invites
    await repo.increment_user_invites(-1001234567890, 111)
    mock_session.execute.assert_called()

    # get_user_invite_stat
    mock_result.scalar_one_or_none.return_value = stat
    user_stat = await repo.get_user_invite_stat(-1001234567890, 111)
    assert user_stat is not None
    assert user_stat.total_invites == 10

    # get_leaderboard
    row_mock = MagicMock()
    row_mock.user_id = 111
    row_mock.username = "top_user"
    row_mock.first_name = "Top"
    row_mock.total_invites = 10
    mock_result.all.return_value = [row_mock]
    lb = await repo.get_leaderboard(-1001234567890, limit=10)
    assert len(lb) == 1
    assert lb[0].user_id == 111
    assert lb[0].total_invites == 10

    # get_chat_invites_for_csv
    csv_row = (111, "top_user", "Top", "User", 10, now)
    mock_result.all.return_value = [csv_row]
    csv_rows = await repo.get_chat_invites_for_csv(-1001234567890)
    assert len(csv_rows) == 1
    assert csv_rows[0][0] == 111
