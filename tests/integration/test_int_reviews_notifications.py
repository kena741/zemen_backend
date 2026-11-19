"""
Integration tests: Reviews & Notifications endpoints.

Covers:
  - Reviews:
    - GET  /api/v1/reviews
    - GET  /api/v1/reviews/by-booking/{booking_id}
    - POST /api/v1/reviews
  - Notifications:
    - GET  /api/v1/notifications
    - GET  /api/v1/notifications/unread/count
    - POST /api/v1/notifications
    - POST /api/v1/notifications/read
    - DELETE /api/v1/notifications/{id}
    - DELETE /api/v1/notifications
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Reviews Endpoints
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_reviews_empty(client: AsyncClient):
    resp = await client.get("/api/v1/reviews")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []


@pytest.mark.asyncio
async def test_get_booking_review_none(client: AsyncClient):
    resp = await client.get(f"/api/v1/reviews/by-booking/{uuid4()}")
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_create_review_unauthenticated_401(client: AsyncClient):
    resp = await client.post(
        "/api/v1/reviews",
        json={"rating": 5.0, "comment": "Great service!"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_review_by_customer_201(customer_client, seed_provider, seed_service, seed_booking):
    client, cust = customer_client
    prov, _, _, _ = await seed_provider()
    svc = await seed_service(provider_id=prov.id)
    bk = await seed_booking(provider_id=prov.id, customer_id=cust.id, service_id=svc.id, status="completed")

    payload = {
        "serviceId": str(svc.id),
        "bookingId": str(bk.id),
        "rating": 4.5,
        "comment": "Prompt and very professional work!",
    }
    resp = await client.post("/api/v1/reviews", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["comment"] == "Prompt and very professional work!"
    assert data["rating"] == 4.5
    assert data["customerId"] == str(cust.id)

    # Verify retrieval by booking id
    get_resp = await client.get(f"/api/v1/reviews/by-booking/{bk.id}")
    assert get_resp.status_code == 200
    review_data = get_resp.json()
    assert review_data is not None
    assert review_data["comment"] == "Prompt and very professional work!"

    # Verify list by service id
    list_resp = await client.get("/api/v1/reviews", params={"serviceId": str(svc.id)})
    assert list_resp.status_code == 200
    assert len(list_resp.json()["items"]) == 1


# ---------------------------------------------------------------------------
# Notifications Endpoints
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_notifications_unauthenticated_401(client: AsyncClient):
    resp = await client.get("/api/v1/notifications")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_notifications_lifecycle(customer_client):
    client, cust = customer_client

    # 1. Unread count initially 0
    cnt_resp = await client.get("/api/v1/notifications/unread/count")
    assert cnt_resp.status_code == 200
    assert cnt_resp.json()["unreadCount"] == 0

    # 2. Create notification
    notif_payload = {
        "title": "Booking Confirmed",
        "body": "Your booking for house cleaning has been accepted.",
        "description": "Provider is on the way.",
    }
    create_resp = await client.post("/api/v1/notifications", json=notif_payload)
    assert create_resp.status_code == 201
    notif = create_resp.json()
    notif_id = notif["id"]
    assert notif["title"] == "Booking Confirmed"
    assert notif["isRead"] is False

    # 3. Unread count is now 1
    cnt_resp2 = await client.get("/api/v1/notifications/unread/count")
    assert cnt_resp2.status_code == 200
    assert cnt_resp2.json()["unreadCount"] == 1

    # 4. List notifications
    list_resp = await client.get("/api/v1/notifications")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == notif_id

    # 5. Mark read
    read_resp = await client.post("/api/v1/notifications/read", json={"ids": [notif_id]})
    assert read_resp.status_code == 200
    assert read_resp.json()["count"] >= 1

    # 6. Delete notification
    del_resp = await client.delete(f"/api/v1/notifications/{notif_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["count"] >= 1

    # 7. List empty
    list_after = await client.get("/api/v1/notifications")
    assert list_after.status_code == 200
    assert list_after.json()["items"] == []
