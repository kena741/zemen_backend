"""
Integration tests: Booking endpoints.

Coverage
--------
GET  /api/v1/bookings           — list customer bookings
POST /api/v1/bookings           — create booking
GET  /api/v1/bookings/provider  — list provider bookings
GET  /api/v1/bookings/{id}     — get booking detail
POST /api/v1/bookings/{id}/accept       — provider accepts
POST /api/v1/bookings/{id}/reject       — provider rejects
POST /api/v1/bookings/{id}/cancel       — customer cancels
POST /api/v1/bookings/{id}/status       — provider updates status
POST /api/v1/bookings/{id}/verify-otp   — verify completion OTP
POST /api/v1/bookings/{id}/service-proof — upload before/after proof
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest


# ============================================================
#  List customer bookings
# ============================================================

@pytest.mark.asyncio
async def test_list_customer_bookings_401_no_token(client):
    resp = await client.get("/api/v1/bookings")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_customer_bookings_403_no_customer_profile(client, seed_provider):
    """A provider without a customer profile is forbidden."""
    prov, user_id, _, token = await seed_provider(phone="+251960000001")
    resp = await client.get(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_customer_bookings_200_empty(customer_client):
    ac, cust = customer_client
    resp = await ac.get("/api/v1/bookings")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert isinstance(body["items"], list)
    assert body["meta"]["limit"] == 50


@pytest.mark.asyncio
async def test_list_customer_bookings_200_with_data(customer_client, seed_booking):
    ac, cust = customer_client
    bk = await seed_booking(customer_id=cust.id)
    resp = await ac.get("/api/v1/bookings")
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()["items"]]
    assert str(bk.id) in ids


@pytest.mark.asyncio
async def test_list_customer_bookings_filtered_by_status(customer_client, seed_booking):
    ac, cust = customer_client
    pending_bk = await seed_booking(customer_id=cust.id, status="pending")
    await seed_booking(customer_id=cust.id, status="accepted")

    resp = await ac.get("/api/v1/bookings?status=pending")
    assert resp.status_code == 200
    items = resp.json()["items"]
    for item in items:
        assert item["status"] == "pending"
    ids = [i["id"] for i in items]
    assert str(pending_bk.id) in ids


@pytest.mark.asyncio
async def test_list_customer_bookings_pagination(customer_client, seed_booking):
    ac, cust = customer_client
    for _ in range(3):
        await seed_booking(customer_id=cust.id)

    resp = await ac.get("/api/v1/bookings?limit=2&offset=0")
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["limit"] == 2
    assert len(body["items"]) <= 2


# ============================================================
#  Create booking
# ============================================================

@pytest.mark.asyncio
async def test_create_booking_401_no_token(client, seed_provider, seed_service):
    prov, prov_uid, _, _ = await seed_provider(phone="+251960000005")
    svc = await seed_service(provider_id=prov.id)
    payload = _booking_payload(prov.id, svc.id)
    resp = await client.post("/api/v1/bookings", json=payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_booking_201(customer_client, seed_provider, seed_service):
    ac, cust = customer_client
    prov, prov_uid, _, _ = await seed_provider(phone="+251960000006")
    svc = await seed_service(provider_id=prov.id)
    payload = _booking_payload(prov.id, svc.id)
    resp = await ac.post("/api/v1/bookings", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "id" in body
    assert body.get("providerId") == str(prov.id)


@pytest.mark.asyncio
async def test_create_booking_422_missing_provider_id(customer_client):
    ac, _ = customer_client
    payload = {
        "firstName": "Test",
        "lastName": "Customer",
        "phoneNumber": "+251911000001",
        "quantity": 1,
        "bookingDate": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "paymentCompleted": False,
        "paymentStatus": "pending_payment",
        "taxList": [],
    }
    resp = await ac.post("/api/v1/bookings", json=payload)
    assert resp.status_code == 422


# ============================================================
#  List provider bookings
# ============================================================

@pytest.mark.asyncio
async def test_list_provider_bookings_401_no_token(client):
    resp = await client.get("/api/v1/bookings/provider")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_provider_bookings_200(provider_client, seed_booking):
    ac, prov = provider_client
    bk = await seed_booking(provider_id=prov.id)
    resp = await ac.get("/api/v1/bookings/provider")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    ids = [i["id"] for i in body["items"]]
    assert str(bk.id) in ids


# ============================================================
#  Get booking detail
# ============================================================

@pytest.mark.asyncio
async def test_get_booking_200(customer_client, seed_booking):
    ac, cust = customer_client
    bk = await seed_booking(customer_id=cust.id)
    resp = await ac.get(f"/api/v1/bookings/{bk.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(bk.id)


@pytest.mark.asyncio
async def test_get_booking_404(customer_client):
    ac, _ = customer_client
    resp = await ac.get(f"/api/v1/bookings/{uuid4()}")
    assert resp.status_code == 404


# ============================================================
#  Lifecycle transitions
# ============================================================

@pytest.mark.asyncio
async def test_provider_accept_booking_200(provider_client, seed_booking):
    ac, prov = provider_client
    bk = await seed_booking(provider_id=prov.id, status="pending")
    resp = await ac.post(f"/api/v1/bookings/{bk.id}/accept")
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_customer_cannot_accept_booking_403(customer_client, seed_booking, seed_provider):
    ac, cust = customer_client
    prov, _, _, _ = await seed_provider(phone="+251960000010")
    bk = await seed_booking(provider_id=prov.id, customer_id=cust.id, status="pending")
    # customer trying to call the provider-only accept endpoint
    resp = await ac.post(f"/api/v1/bookings/{bk.id}/accept")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_provider_reject_booking_200(provider_client, seed_booking):
    ac, prov = provider_client
    bk = await seed_booking(provider_id=prov.id, status="pending")
    resp = await ac.post(
        f"/api/v1/bookings/{bk.id}/reject",
        json={"reason": "Unavailable on that date"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("rejected", "declined")


@pytest.mark.asyncio
async def test_customer_cancel_booking_200(customer_client, seed_booking, seed_provider):
    ac, cust = customer_client
    prov, _, _, _ = await seed_provider(phone="+251960000011")
    bk = await seed_booking(provider_id=prov.id, customer_id=cust.id, status="accepted")
    resp = await ac.post(
        f"/api/v1/bookings/{bk.id}/cancel",
        json={"reason": "Changed my mind"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_cancel_requires_customer_role(provider_client, seed_booking):
    ac, prov = provider_client
    bk = await seed_booking(provider_id=prov.id, status="accepted")
    resp = await ac.post(
        f"/api/v1/bookings/{bk.id}/cancel",
        json={"reason": "Provider trying to cancel"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_verify_otp_invalid(client, seed_booking):
    bk = await seed_booking(otp="123456")
    resp = await client.post(
        f"/api/v1/bookings/{bk.id}/verify-otp",
        json={"otp": "000000"},
    )
    assert resp.status_code == 200
    assert resp.json().get("valid") is False


# ============================================================
#  Helpers
# ============================================================

def _booking_payload(provider_id, service_id=None) -> dict:
    return {
        "providerId": str(provider_id),
        "serviceId": str(service_id) if service_id else None,
        "serviceName": "House Cleaning",
        "firstName": "Test",
        "lastName": "Customer",
        "phoneNumber": "+251911000001",
        "price": 500.0,
        "quantity": 1,
        "bookingDate": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        "paymentCompleted": False,
        "paymentStatus": "pending_payment",
        "taxList": [],
        "totalAmount": 550.0,
        "subTotal": 500.0,
        "bookingAddress": {"address": "Addis Ababa, Ethiopia"},
    }
