"""Integration tests for Chats, Telegram, and Storage/Media endpoints.

Covers:
  - Chats:
    - GET    /api/v1/chats/unread/count
    - GET    /api/v1/chats/inbox
    - POST   /api/v1/chats/send
    - GET    /api/v1/chats/{peer_id}/messages
    - POST   /api/v1/chats/{peer_id}/seen
    - DELETE /api/v1/chats/{peer_id}
  - Telegram:
    - POST   /api/v1/telegram/webhook (403 forbidden on missing/bad secret, 200 on valid)
    - GET    /api/v1/telegram/chats
    - GET    /api/v1/telegram/chats/{chat_id}
    - GET    /api/v1/telegram/stats/{chat_id}/leaderboard
  - Storage:
    - POST   /api/v1/storage/upload
    - DELETE /api/v1/storage/delete
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.config import settings


# ===========================================================================
# Chats Endpoints
# ===========================================================================


@pytest.mark.asyncio
async def test_chats_unread_count_unauthenticated_401(client: AsyncClient):
    """GET /api/v1/chats/unread/count without auth returns 401."""
    resp = await client.get("/api/v1/chats/unread/count")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_chats_unread_count_authenticated_200(customer_client):
    """GET /api/v1/chats/unread/count returns unread count."""
    client, cust = customer_client
    resp = await client.get("/api/v1/chats/unread/count")
    assert resp.status_code == 200
    assert "unreadCount" in resp.json()


@pytest.mark.asyncio
async def test_chats_inbox_empty_200(customer_client):
    """GET /api/v1/chats/inbox returns paginated inbox list."""
    client, cust = customer_client
    resp = await client.get("/api/v1/chats/inbox")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_chats_full_conversation_lifecycle(
    client: AsyncClient,
    seed_customer,
    seed_provider,
):
    """Customer sends a message to provider, lists messages, marks seen, clears conversation."""
    cust, _, _, c_token = await seed_customer()
    prov, _, _, p_token = await seed_provider()
    c_headers = {"Authorization": f"Bearer {c_token}"}
    p_headers = {"Authorization": f"Bearer {p_token}"}

    receiver_id = str(prov.id)

    # 1. Customer sends message
    send_payload = {
        "receiverId": receiver_id,
        "message": "Hello, are you available tomorrow?",
        "type": "text",
    }
    resp = await client.post("/api/v1/chats/send", json=send_payload, headers=c_headers)
    assert resp.status_code == 201
    msg_data = resp.json()
    assert msg_data["message"] == "Hello, are you available tomorrow?"

    # 2. Provider lists conversation messages with customer
    resp = await client.get(f"/api/v1/chats/{cust.id}/messages", headers=p_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(m["message"] == "Hello, are you available tomorrow?" for m in items)

    # 3. Provider marks conversation as seen
    resp = await client.post(f"/api/v1/chats/{cust.id}/seen", headers=p_headers)
    assert resp.status_code == 200

    # 4. Clear conversation
    resp = await client.delete(f"/api/v1/chats/{receiver_id}", headers=c_headers)
    assert resp.status_code == 200


# ===========================================================================
# Telegram Endpoints
# ===========================================================================


@pytest.mark.asyncio
async def test_telegram_webhook_missing_secret_403(client: AsyncClient):
    """POST /api/v1/telegram/webhook without secret header returns 403."""
    resp = await client.post("/api/v1/telegram/webhook", json={"update_id": 9999})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_telegram_webhook_valid_secret_200(client: AsyncClient):
    """POST /api/v1/telegram/webhook with valid secret header returns 200."""
    headers = {"X-Telegram-Bot-Api-Secret-Token": settings.TELEGRAM_WEBHOOK_SECRET}
    payload = {"update_id": 10001}
    resp = await client.post("/api/v1/telegram/webhook", json=payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_telegram_chats_list_200(client: AsyncClient):
    """GET /api/v1/telegram/chats returns list of tracked Telegram chats."""
    resp = await client.get("/api/v1/telegram/chats")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_telegram_chat_not_found_404(client: AsyncClient):
    """GET /api/v1/telegram/chats/{chat_id} for unknown chat returns 404."""
    resp = await client.get("/api/v1/telegram/chats/-999999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_telegram_leaderboard_200(client: AsyncClient):
    """GET /api/v1/telegram/stats/{chat_id}/leaderboard returns list."""
    resp = await client.get("/api/v1/telegram/stats/-1001234567/leaderboard")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ===========================================================================
# Storage Endpoints
# ===========================================================================


@pytest.mark.asyncio
async def test_storage_upload_and_delete(client: AsyncClient):
    """POST /api/v1/storage/upload and DELETE /api/v1/storage/delete with mocked GCS."""
    with patch(
        "app.core.storage.gcs.GCSStorageService.upload_bytes_async",
        new_callable=AsyncMock,
        return_value="https://storage.googleapis.com/test-bucket/media/sample.png",
    ), patch(
        "app.core.storage.gcs.GCSStorageService.delete_by_public_url_async",
        new_callable=AsyncMock,
        return_value=True,
    ):
        files = {"file": ("test.png", b"\x89PNG\r\n\x1a\nfakeimagecontent", "image/png")}
        resp = await client.post("/api/v1/storage/upload", files=files)
        assert resp.status_code == 201
        data = resp.json()
        assert "url" in data
        assert "storage.googleapis.com" in data["url"]

        del_resp = await client.delete(
            "/api/v1/storage/delete",
            params={"url": data["url"]},
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["deleted"] is True
