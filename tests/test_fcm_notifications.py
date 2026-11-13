"""Tests for FCM push notification service in mock/dry-run mode."""

from app.core.notifications.fcm import (
    send_fcm_notification,
    send_multicast_fcm_notification,
)


def test_fcm_mock_single_send():
    res = send_fcm_notification(
        token="sample_fcm_device_token",
        title="Test Notification",
        body="Hello world",
        data={"key": "val"},
    )
    assert res is not None


def test_fcm_empty_token_returns_none():
    assert send_fcm_notification("", "Title", "Body") is None
    assert send_fcm_notification("   ", "Title", "Body") is None


def test_fcm_mock_multicast():
    tokens = ["token_1", "token_2", ""]
    count = send_multicast_fcm_notification(
        tokens=tokens,
        title="Multicast Test",
        body="Broadcast alert",
    )
    assert count == 2

