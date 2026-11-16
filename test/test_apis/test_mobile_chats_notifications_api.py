"""Integration tests for Mobile Chat and Notification APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1.routers.chats import get_chat_service
from app.api.v1.routers.notifications import get_notification_service
from app.core.security.deps import AuthContext
from app.domain.chat import ChatInboxDomain, ChatMessageDomain
from app.domain.notification import NotificationDomain


@pytest.fixture
def mock_chat_service():
    return AsyncMock()


@pytest.fixture
def mock_notification_service():
    return AsyncMock()


def test_chat_endpoints(api_client, mock_chat_service):
    user_id = uuid4()
    cust_id = uuid4()
    now = datetime.now(timezone.utc)

    client = api_client(
        auth_context=AuthContext(user_id=user_id, email="test@zemen.com", roles=["customer"], customer_id=cust_id)
    )
    client.app.dependency_overrides[get_chat_service] = lambda: mock_chat_service

    # 1. Unread count
    mock_chat_service.get_unread_count.return_value = 3
    res_cnt = client.get("/api/v1/chats/unread/count")
    assert res_cnt.status_code == 200
    assert res_cnt.json()["unreadCount"] == 3

    # 2. Send message via /send
    msg_domain = ChatMessageDomain(
        chat_id="msg_101",
        sender_id=str(cust_id),
        receiver_id="peer_202",
        message="Hello provider!",
        media_url=None,
        seen=False,
        type="text",
        timestamp=now,
        created_at=now,
    )
    mock_chat_service.send_message.return_value = msg_domain
    res_send = client.post(
        "/api/v1/chats/send",
        json={"receiverId": "peer_202", "message": "Hello provider!"},
    )
    assert res_send.status_code == 201
    assert res_send.json()["chatID"] == "msg_101"
    assert res_send.json()["senderId"] == str(cust_id)
    assert res_send.json()["receiverId"] == "peer_202"

    # 3. List inbox
    mock_chat_service.list_inbox.return_value = [
        ChatInboxDomain(
            id=f"{cust_id}_peer_202",
            sender_id=str(cust_id),
            receiver_id="peer_202",
            last_message="Hello provider!",
            timestamp=now,
        )
    ]
    res_inbox = client.get("/api/v1/chats/inbox")
    assert res_inbox.status_code == 200
    assert len(res_inbox.json()["items"]) == 1
    assert res_inbox.json()["items"][0]["lastMessage"] == "Hello provider!"

    # 4. List messages with peer
    mock_chat_service.list_conversation.return_value = [msg_domain]
    res_msgs = client.get("/api/v1/chats/peer_202/messages")
    assert res_msgs.status_code == 200
    assert len(res_msgs.json()["items"]) == 1
    assert res_msgs.json()["items"][0]["chatID"] == "msg_101"

    # 5. Send message with peer in path
    mock_chat_service.send_message.return_value = msg_domain
    res_peer_send = client.post(
        "/api/v1/chats/peer_202/messages",
        json={"message": "Second message"},
    )
    assert res_peer_send.status_code == 201
    assert res_peer_send.json()["chatID"] == "msg_101"

    # 6. Mark seen
    mock_chat_service.mark_seen.return_value = None
    res_seen = client.post("/api/v1/chats/peer_202/seen")
    assert res_seen.status_code == 200
    assert res_seen.json()["count"] == 1

    # 7. Delete message
    mock_chat_service.delete_message.return_value = True
    res_del_msg = client.delete("/api/v1/chats/peer_202/messages/msg_101")
    assert res_del_msg.status_code == 200
    assert res_del_msg.json()["count"] == 1

    # 8. Clear conversation
    mock_chat_service.clear_conversation.return_value = 8
    res_clr = client.delete("/api/v1/chats/peer_202")
    assert res_clr.status_code == 200
    assert res_clr.json()["count"] == 8


def test_notification_endpoints(api_client, mock_notification_service):
    user_id = uuid4()
    cust_id = uuid4()
    nid = uuid4()
    now = datetime.now(timezone.utc)

    client = api_client(
        auth_context=AuthContext(user_id=user_id, email="test@zemen.com", roles=["customer"], customer_id=cust_id)
    )
    client.app.dependency_overrides[get_notification_service] = lambda: mock_notification_service

    # 1. Unread count
    mock_notification_service.get_unread_count.return_value = 4
    res_cnt = client.get("/api/v1/notifications/unread/count")
    assert res_cnt.status_code == 200
    assert res_cnt.json()["unreadCount"] == 4

    # 2. List notifications
    notif_domain = NotificationDomain(
        id=nid,
        title="Service Booked",
        description="Booking #101 has been confirmed",
        type="booking",
        is_read=False,
        recipient_role="customer",
        created_at=now,
    )
    mock_notification_service.list_notifications.return_value = [notif_domain]
    res_list = client.get("/api/v1/notifications")
    assert res_list.status_code == 200
    assert len(res_list.json()["items"]) == 1
    assert res_list.json()["items"][0]["title"] == "Service Booked"
    assert res_list.json()["items"][0]["isRead"] is False

    # 3. Create notification (setNotification)
    mock_notification_service.create_notification.return_value = notif_domain
    res_create = client.post(
        "/api/v1/notifications",
        json={"title": "Service Booked", "description": "Booking #101 has been confirmed", "type": "booking"},
    )
    assert res_create.status_code == 201
    assert res_create.json()["id"] == str(nid)

    # 4. Mark read
    mock_notification_service.mark_ids_read.return_value = 1
    res_read = client.post(
        "/api/v1/notifications/read",
        json={"ids": [str(nid)]},
    )
    assert res_read.status_code == 200
    assert res_read.json()["count"] == 1

    # 5. Send push notification
    mock_notification_service.send_push_notification.return_value = True
    res_push = client.post(
        "/api/v1/notifications/send-push",
        json={
            "token": "fcm_test_token_123",
            "title": "Alert",
            "body": "Push content",
        },
    )
    assert res_push.status_code == 200
    assert res_push.json()["success"] is True

    # 6. Delete one notification
    mock_notification_service.delete_notifications.return_value = 1
    res_del_one = client.delete(f"/api/v1/notifications/{nid}")
    assert res_del_one.status_code == 200
    assert res_del_one.json()["count"] == 1

    # 7. Clear all notifications
    mock_notification_service.delete_notifications.return_value = 5
    res_clr_all = client.delete("/api/v1/notifications")
    assert res_clr_all.status_code == 200
    assert res_clr_all.json()["count"] == 5
