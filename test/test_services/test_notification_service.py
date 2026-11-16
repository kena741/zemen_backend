from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.services.notification_service import NotificationService
from app.domain.exceptions import EntityNotFoundError
from app.domain.notification import NotificationDomain


@pytest.fixture
def mock_notif_repo():
    return AsyncMock()


@pytest.fixture
def notif_service(mock_notif_repo):
    return NotificationService(mock_notif_repo)


@pytest.mark.asyncio
async def test_list_notifications(notif_service, mock_notif_repo):
    actor_id = uuid4()
    mock_notif_repo.list_for_actor.return_value = [
        NotificationDomain(
            id=uuid4(),
            title="Booking Confirmed",
            description="Your booking is confirmed",
            type="booking",
            is_read=False,
            recipient_role="customer",
            created_at=datetime.now(timezone.utc),
        )
    ]

    res = await notif_service.list_notifications(actor_id=actor_id, limit=20, offset=0)
    assert len(res) == 1
    assert res[0].title == "Booking Confirmed"
    mock_notif_repo.list_for_actor.assert_awaited_once_with(actor_id=actor_id, limit=20, offset=0)


@pytest.mark.asyncio
async def test_create_notification(notif_service, mock_notif_repo):
    nid = uuid4()
    mock_notif_repo.create_notification.return_value = NotificationDomain(
        id=nid,
        title="New Message",
        description="You have a new message",
        type="chat",
        is_read=False,
        recipient_role="customer",
        created_at=datetime.now(timezone.utc),
    )

    created = await notif_service.create_notification({"title": "New Message"})
    assert created.id == nid
    assert created.type == "chat"
    mock_notif_repo.create_notification.assert_awaited_once_with({"title": "New Message"})


@pytest.mark.asyncio
async def test_mark_read_success(notif_service, mock_notif_repo):
    nid = uuid4()
    mock_notif_repo.mark_as_read.return_value = True

    marked = await notif_service.mark_read(nid)
    assert marked is True
    mock_notif_repo.mark_as_read.assert_awaited_once_with(nid)


@pytest.mark.asyncio
async def test_mark_read_not_found(notif_service, mock_notif_repo):
    nid = uuid4()
    mock_notif_repo.mark_as_read.return_value = False

    with pytest.raises(EntityNotFoundError):
        await notif_service.mark_read(nid)


@pytest.mark.asyncio
async def test_mark_ids_read(notif_service, mock_notif_repo):
    actor_id = uuid4()
    ids = [uuid4(), uuid4()]
    mock_notif_repo.mark_ids_read.return_value = 2

    cnt = await notif_service.mark_ids_read(actor_id=actor_id, ids=ids)
    assert cnt == 2
    mock_notif_repo.mark_ids_read.assert_awaited_once_with(actor_id=actor_id, ids=ids)


@pytest.mark.asyncio
async def test_mark_all_read(notif_service, mock_notif_repo):
    actor_id = uuid4()
    mock_notif_repo.mark_all_read.return_value = 5

    cnt = await notif_service.mark_all_read(actor_id=actor_id)
    assert cnt == 5
    mock_notif_repo.mark_all_read.assert_awaited_once_with(actor_id=actor_id)


@pytest.mark.asyncio
async def test_delete_notifications(notif_service, mock_notif_repo):
    actor_id = uuid4()
    ids = [uuid4()]
    mock_notif_repo.delete_owned.return_value = 1

    cnt = await notif_service.delete_notifications(actor_id=actor_id, ids=ids)
    assert cnt == 1
    mock_notif_repo.delete_owned.assert_awaited_once_with(actor_id=actor_id, ids=ids)


@pytest.mark.asyncio
async def test_get_unread_count(notif_service, mock_notif_repo):
    actor_id = uuid4()
    mock_notif_repo.count_unread.return_value = 3

    cnt = await notif_service.get_unread_count(actor_id=actor_id)
    assert cnt == 3
    mock_notif_repo.count_unread.assert_awaited_once_with(actor_id=actor_id)


@pytest.mark.asyncio
async def test_send_push_notification_no_token(notif_service):
    res = await notif_service.send_push_notification(
        fcm_token=None,
        title="Test",
        body="Body",
    )
    assert res is False

