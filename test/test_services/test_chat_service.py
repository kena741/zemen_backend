from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.services.chat_service import ChatService
from app.domain.chat import ChatInboxDomain, ChatMessageDomain
from app.domain.exceptions import ValidationError


@pytest.fixture
def mock_chat_repo():
    return AsyncMock()


@pytest.fixture
def chat_service(mock_chat_repo):
    return ChatService(mock_chat_repo)


@pytest.mark.asyncio
async def test_send_message_validation(chat_service):
    # Empty message and media
    with pytest.raises(ValidationError, match="Message text or mediaUrl must be provided"):
        await chat_service.send_message(sender_id="user1", receiver_id="user2", message="", media_url="")

    # Message to self
    with pytest.raises(ValidationError, match="Cannot send message to yourself"):
        await chat_service.send_message(sender_id="user1", receiver_id="user1", message="Hello")


@pytest.mark.asyncio
async def test_send_message_success(chat_service, mock_chat_repo):
    now = datetime.now(timezone.utc)
    mock_chat_repo.insert_message.return_value = ChatMessageDomain(
        chat_id="msg1",
        sender_id="user1",
        receiver_id="user2",
        message="Hello there",
        media_url=None,
        seen=False,
        type="text",
        timestamp=now,
        created_at=now,
    )

    result = await chat_service.send_message(
        sender_id="user1",
        receiver_id="user2",
        message="Hello there",
    )

    assert result.chat_id == "msg1"
    assert result.message == "Hello there"
    mock_chat_repo.insert_message.assert_awaited_once_with(
        sender_id="user1",
        receiver_id="user2",
        message="Hello there",
        media_url=None,
        msg_type="text",
        chat_id=None,
    )


@pytest.mark.asyncio
async def test_list_conversation(chat_service, mock_chat_repo):
    now = datetime.now(timezone.utc)
    mock_chat_repo.list_messages.return_value = [
        ChatMessageDomain(
            chat_id="msg1",
            sender_id="user1",
            receiver_id="user2",
            message="Hi",
            timestamp=now,
            created_at=now,
        )
    ]

    messages = await chat_service.list_conversation("user1", "user2", limit=20, offset=0)
    assert len(messages) == 1
    assert messages[0].chat_id == "msg1"
    mock_chat_repo.list_messages.assert_awaited_once_with(
        user_id="user1", peer_id="user2", limit=20, offset=0
    )


@pytest.mark.asyncio
async def test_list_inbox(chat_service, mock_chat_repo):
    now = datetime.now(timezone.utc)
    mock_chat_repo.list_inbox.return_value = [
        ChatInboxDomain(
            id="user1_user2",
            sender_id="user1",
            receiver_id="user2",
            last_message="Hi",
            timestamp=now,
        )
    ]

    inbox = await chat_service.list_inbox("user1")
    assert len(inbox) == 1
    assert inbox[0].id == "user1_user2"
    mock_chat_repo.list_inbox.assert_awaited_once_with(user_id="user1", limit=50, offset=0)


@pytest.mark.asyncio
async def test_mark_seen(chat_service, mock_chat_repo):
    mock_chat_repo.mark_messages_seen.return_value = None
    await chat_service.mark_seen("user1", "user2")
    mock_chat_repo.mark_messages_seen.assert_awaited_once_with(user_id="user1", peer_id="user2")


@pytest.mark.asyncio
async def test_unread_count(chat_service, mock_chat_repo):
    mock_chat_repo.count_unread_messages.return_value = 5
    cnt = await chat_service.get_unread_count("user1")
    assert cnt == 5
    mock_chat_repo.count_unread_messages.assert_awaited_once_with(user_id="user1")


@pytest.mark.asyncio
async def test_delete_message(chat_service, mock_chat_repo):
    mock_chat_repo.delete_message.return_value = True
    deleted = await chat_service.delete_message("user1", "user2", "msg1")
    assert deleted is True
    mock_chat_repo.delete_message.assert_awaited_once_with(
        user_id="user1", peer_id="user2", chat_id="msg1"
    )


@pytest.mark.asyncio
async def test_clear_conversation(chat_service, mock_chat_repo):
    mock_chat_repo.clear_conversation.return_value = 10
    cnt = await chat_service.clear_conversation("user1", "user2")
    assert cnt == 10
    mock_chat_repo.clear_conversation.assert_awaited_once_with(
        user_id="user1", peer_id="user2"
    )

