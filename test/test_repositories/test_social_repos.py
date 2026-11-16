"""Unit tests for Chat, Notification, and Review repositories."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.persistence.repositories.chat_repo import ChatRepository
from app.persistence.repositories.notification_repo import NotificationRepository
from app.persistence.repositories.review_repo import ReviewRepository
from app.persistence.sqlalchemy.models.social import ChatInbox, ChatMessage, Notification, ReviewCustomer
from .conftest import RepoMockSession


def test_chat_repo_conversation_id_deterministic():
    u1 = "user_bbb"
    u2 = "user_aaa"
    # Regardless of order, conversation id is sorted
    assert ChatRepository.conversation_id(u1, u2) == "user_aaa_user_bbb"
    assert ChatRepository.conversation_id(u2, u1) == "user_aaa_user_bbb"


def test_chat_repo_to_domain():
    now = datetime.now(timezone.utc)
    msg_entity = ChatMessage(
        chat_id="c_123",
        sender_id="s_1",
        receiver_id="r_2",
        message="Hello",
        media_url="https://img.com/a.png",
        seen=True,
        type="image",
        timestamp=now,
        created_at=now,
    )
    session = RepoMockSession()
    repo = ChatRepository(session)  # type: ignore[arg-type]

    domain = repo.to_message_domain(msg_entity)
    assert domain.chat_id == "c_123"
    assert domain.sender_id == "s_1"
    assert domain.receiver_id == "r_2"
    assert domain.message == "Hello"
    assert domain.media_url == "https://img.com/a.png"
    assert domain.seen is True
    assert domain.type == "image"

    inbox_entity = ChatInbox(
        id="s_1_r_2",
        sender_id="s_1",
        receiver_id="r_2",
        last_message="Hello",
        media_url="https://img.com/a.png",
        seen=True,
        type="image",
        timestamp=now,
        archive=False,
    )
    inbox_domain = repo.to_inbox_domain(inbox_entity)
    assert inbox_domain.id == "s_1_r_2"
    assert inbox_domain.last_message == "Hello"
    assert inbox_domain.archive is False


def test_notification_repo_to_domain_and_filter():
    nid = uuid4()
    cust_id = uuid4()
    prov_id = uuid4()
    now = datetime.now(timezone.utc)

    notif_entity = Notification(
        id=nid,
        title="Accepted",
        description="Your booking was accepted",
        type="booking",
        is_read=False,
        recipient_role="customer",
        created_at=now,
        customer_id=cust_id,
        provider_id=prov_id,
    )

    session = RepoMockSession()
    repo = NotificationRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(notif_entity)
    assert domain.id == nid
    assert domain.title == "Accepted"
    assert domain.customer_id == cust_id
    assert domain.provider_id == prov_id

    # Filter generation with list of UUIDs
    clause = repo._actor_filter([cust_id, prov_id])
    assert clause is not None

    # Empty filter returns None
    assert repo._actor_filter([]) is None


def test_review_repo_to_domain():
    rid = uuid4()
    cid = uuid4()
    sid = uuid4()
    now = datetime.now(timezone.utc)

    rc_entity = ReviewCustomer(
        id=rid,
        comment="Great experience",
        rating="4.5",
        customer_id=cid,
        service_id=sid,
        date=now,
    )

    session = RepoMockSession()
    repo = ReviewRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(rc_entity, customer_name="Almaz Ayana", customer_image="https://img.com/profile.jpg")
    assert domain.id == rid
    assert domain.comment == "Great experience"
    assert domain.rating == 4.5
    assert domain.customer_name == "Almaz Ayana"
    assert domain.customer_image == "https://img.com/profile.jpg"

