from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.config import settings
from app.persistence.sqlalchemy.deps import get_db
from test.test_apis.conftest import ApiTestDbSession


@pytest.fixture
def test_client():
    app = create_app()
    client = TestClient(app)
    return client


def test_telegram_webhook_rejected_when_missing_secret(test_client, monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "super-secret-token")

    payload = {
        "update_id": 1001,
        "chat_member": {
            "chat": {"id": -1001234567890, "title": "Test Group", "type": "supergroup"},
            "from": {"id": 111111, "first_name": "Inviter User", "is_bot": False},
            "date": int(datetime.now(timezone.utc).timestamp()),
            "old_chat_member": {
                "user": {"id": 222222, "first_name": "Joined User", "is_bot": False},
                "status": "left",
            },
            "new_chat_member": {
                "user": {"id": 222222, "first_name": "Joined User", "is_bot": False},
                "status": "member",
            },
        },
    }

    # Request without X-Telegram-Bot-Api-Secret-Token
    response = test_client.post("/api/v1/telegram/webhook", json=payload)
    assert response.status_code == 403
    assert response.json()["detail"] == "Missing secret token"


def test_telegram_webhook_rejected_when_invalid_secret(test_client, monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "super-secret-token")

    payload = {
        "update_id": 1001,
        "chat_member": {
            "chat": {"id": -1001234567890, "title": "Test Group", "type": "supergroup"},
            "from": {"id": 111111, "first_name": "Inviter User", "is_bot": False},
            "date": int(datetime.now(timezone.utc).timestamp()),
            "old_chat_member": {
                "user": {"id": 222222, "first_name": "Joined User", "is_bot": False},
                "status": "left",
            },
            "new_chat_member": {
                "user": {"id": 222222, "first_name": "Joined User", "is_bot": False},
                "status": "member",
            },
        },
    }

    response = test_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret-token"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid secret token"


def test_telegram_webhook_success_with_valid_secret(test_client, monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "super-secret-token")

    payload = {
        "update_id": 1001,
        "chat_member": {
            "chat": {"id": -1001234567890, "title": "Test Group", "type": "supergroup"},
            "from": {"id": 111111, "first_name": "Inviter User", "is_bot": False},
            "date": int(datetime.now(timezone.utc).timestamp()),
            "old_chat_member": {
                "user": {"id": 222222, "first_name": "Joined User", "is_bot": False},
                "status": "left",
            },
            "new_chat_member": {
                "user": {"id": 222222, "first_name": "Joined User", "is_bot": False},
                "status": "member",
            },
        },
    }

    with patch(
        "app.core.services.telegram_service.process_telegram_webhook_update",
        new=AsyncMock(return_value={"handled": True}),
    ):
        response = test_client.post(
            "/api/v1/telegram/webhook",
            json=payload,
            headers={"X-Telegram-Bot-Api-Secret-Token": "super-secret-token"},
        )
        assert response.status_code == 200
        assert response.json() == {"ok": True, "message": None}


def test_telegram_webhook_success_invite_link_payload(test_client, monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "super-secret-token")

    payload = {
        "update_id": 1002,
        "chat_member": {
            "chat": {"id": -1001234567890, "title": "Test Channel", "type": "channel"},
            "from": {"id": 222222, "first_name": "Joined User", "is_bot": False},
            "date": int(datetime.now(timezone.utc).timestamp()),
            "old_chat_member": {
                "user": {"id": 222222, "first_name": "Joined User", "is_bot": False},
                "status": "left",
            },
            "new_chat_member": {
                "user": {"id": 222222, "first_name": "Joined User", "is_bot": False},
                "status": "member",
            },
            "invite_link": {
                "invite_link": "https://t.me/+AbCdEfGhIjK",
                "creator": {
                    "id": 999999,
                    "first_name": "Affiliate Marketer",
                    "username": "affiliate_pro",
                    "is_bot": False,
                },
                "name": "Summer Campaign",
                "is_primary": False,
            },
        },
    }

    with patch(
        "app.core.services.telegram_service.process_telegram_webhook_update",
        new=AsyncMock(return_value={"handled": True, "incremented": True}),
    ):
        response = test_client.post(
            "/api/v1/telegram/webhook",
            json=payload,
            headers={"X-Telegram-Bot-Api-Secret-Token": "super-secret-token"},
        )
        assert response.status_code == 200
        assert response.json()["ok"] is True


def test_telegram_get_stats_found(test_client):
    from unittest.mock import MagicMock
    mock_stat = MagicMock()
    mock_stat.chat_id = -1001234567890
    mock_stat.user_id = 111111
    mock_stat.total_invites = 42
    mock_stat.updated_at = datetime.now(timezone.utc)

    with patch(
        "app.core.services.telegram_service.get_user_invite_stats",
        new=AsyncMock(return_value=mock_stat),
    ):
        response = test_client.get("/api/v1/telegram/stats/-1001234567890/111111")
        assert response.status_code == 200
        data = response.json()
        assert data["chat_id"] == -1001234567890
        assert data["user_id"] == 111111
        assert data["total_invites"] == 42


def test_telegram_get_stats_not_found(test_client):
    with patch(
        "app.core.services.telegram_service.get_user_invite_stats",
        new=AsyncMock(return_value=None),
    ):
        response = test_client.get("/api/v1/telegram/stats/-1001234567890/999999")
        assert response.status_code == 404
        assert response.json()["detail"] == "No invite statistics found for this user in this chat"


def test_telegram_leaderboard(test_client):
    from app.api.v1.schemas.telegram import TelegramLeaderboardEntry

    mock_entries = [
        TelegramLeaderboardEntry(
            user_id=111, username="top_inviter", first_name="Alice", total_invites=15
        ),
        TelegramLeaderboardEntry(
            user_id=222, username="runner_up", first_name="Bob", total_invites=8
        ),
    ]

    with patch(
        "app.core.services.telegram_service.get_chat_leaderboard",
        new=AsyncMock(return_value=mock_entries),
    ):
        response = test_client.get("/api/v1/telegram/stats/-1001234567890/leaderboard?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["username"] == "top_inviter"
        assert data[0]["total_invites"] == 15
        assert data[1]["first_name"] == "Bob"
        assert data[1]["total_invites"] == 8

