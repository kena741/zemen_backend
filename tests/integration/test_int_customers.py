"""
Integration tests: /api/v1/customers endpoints.

Covers:
  - GET  /api/v1/customers/check-phone
  - GET  /api/v1/customers/by-phone
  - GET  /api/v1/customers/by-email
  - GET  /api/v1/customers/{customer_id}
  - GET  /api/v1/customers/me
  - PATCH /api/v1/customers/me
  - PUT  /api/v1/customers/me/fcm-token
  - DELETE /api/v1/customers/me
  - GET  /api/v1/customers/me/service-details
  - PUT  /api/v1/customers/me/service-details
  - DELETE /api/v1/customers/me/service-details/{detail_id}
"""

import secrets
from uuid import uuid4

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Public lookup endpoints
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_check_phone_registered_true(client: AsyncClient, seed_customer):
    cust, _, _, _ = await seed_customer()
    phone = cust.phone
    resp = await client.get("/api/v1/customers/check-phone", params={"phone": phone})
    assert resp.status_code == 200
    data = resp.json()
    assert data["isRegistered"] is True
    assert data["phone"] == phone


@pytest.mark.asyncio
async def test_check_phone_registered_false(client: AsyncClient):
    unregistered_phone = "+251999999999"
    resp = await client.get("/api/v1/customers/check-phone", params={"phone": unregistered_phone})
    assert resp.status_code == 200
    data = resp.json()
    assert data["isRegistered"] is False
    assert data["phone"] == unregistered_phone


@pytest.mark.asyncio
async def test_check_phone_missing_param_422(client: AsyncClient):
    resp = await client.get("/api/v1/customers/check-phone")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_check_phone_short_param_422(client: AsyncClient):
    resp = await client.get("/api/v1/customers/check-phone", params={"phone": "12"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_customer_by_phone_200(client: AsyncClient, seed_customer):
    cust, _, _, _ = await seed_customer()
    phone = cust.phone
    resp = await client.get("/api/v1/customers/by-phone", params={"phone": phone})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(cust.id)
    assert data["phone"] == phone


@pytest.mark.asyncio
async def test_get_customer_by_phone_404(client: AsyncClient):
    resp = await client.get("/api/v1/customers/by-phone", params={"phone": "+251900000000"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_customer_by_email_200(client: AsyncClient, seed_customer):
    test_email = f"cust_{secrets.token_hex(4)}@example.com"
    cust, _, _, _ = await seed_customer(email=test_email)
    resp = await client.get("/api/v1/customers/by-email", params={"email": test_email})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(cust.id)
    assert data["email"] == test_email


@pytest.mark.asyncio
async def test_get_customer_by_email_404(client: AsyncClient):
    resp = await client.get("/api/v1/customers/by-email", params={"email": "nonexistent@example.com"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Authenticated endpoints: Profile
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_my_profile_401_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/v1/customers/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_my_profile_403_for_provider(provider_client):
    client, _ = provider_client
    resp = await client.get("/api/v1/customers/me")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_my_profile_200(customer_client):
    client, cust = customer_client
    resp = await client.get("/api/v1/customers/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(cust.id)
    assert data["phone"] == cust.phone
    assert data["firstName"] == cust.first_name
    assert data["lastName"] == cust.last_name


@pytest.mark.asyncio
async def test_update_my_profile_200(customer_client):
    client, cust = customer_client
    payload = {
        "firstName": "UpdatedFirst",
        "lastName": "UpdatedLast",
        "address": {"city": "Addis Ababa", "street": "Bole Road"},
    }
    resp = await client.patch("/api/v1/customers/me", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["firstName"] == "UpdatedFirst"
    assert data["lastName"] == "UpdatedLast"
    assert data["address"]["city"] == "Addis Ababa"


@pytest.mark.asyncio
async def test_update_fcm_token_200(customer_client):
    client, cust = customer_client
    resp = await client.put("/api/v1/customers/me/fcm-token", json={"fcmToken": "sample_fcm_token_12345"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["fcmToken"] == "sample_fcm_token_12345"


@pytest.mark.asyncio
async def test_update_fcm_token_missing_422(customer_client):
    client, _ = customer_client
    resp = await client.put("/api/v1/customers/me/fcm-token", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_archive_my_profile_200(customer_client):
    client, cust = customer_client
    resp = await client.delete("/api/v1/customers/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(cust.id)


@pytest.mark.asyncio
async def test_get_customer_by_id_200(customer_client, seed_customer):
    client, current_cust = customer_client
    other_cust, _, _, _ = await seed_customer()
    resp = await client.get(f"/api/v1/customers/{other_cust.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(other_cust.id)


@pytest.mark.asyncio
async def test_get_customer_by_id_404(customer_client):
    client, _ = customer_client
    resp = await client.get(f"/api/v1/customers/{uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Saved Service Details
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_saved_service_details_empty(customer_client):
    client, cust = customer_client
    resp = await client.get("/api/v1/customers/me/service-details")
    assert resp.status_code == 200
    data = resp.json()
    assert data["customerId"] == str(cust.id)
    assert data["serviceDetailsList"] == []


@pytest.mark.asyncio
async def test_replace_and_delete_service_details(customer_client):
    client, cust = customer_client
    payload = {
        "serviceDetailsList": [
            {
                "serviceName": "Draft Painting",
                "description": "Full living room paint",
                "price": 1200.0,
                "serviceImage": ["https://example.com/paint.jpg"],
            }
        ]
    }
    resp = await client.put("/api/v1/customers/me/service-details", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["serviceDetailsList"]) == 1
    detail_id = data["serviceDetailsList"][0]["id"]

    # Delete that single detail
    del_resp = await client.delete(f"/api/v1/customers/me/service-details/{detail_id}")
    assert del_resp.status_code == 204

    # Verify empty now
    get_resp = await client.get("/api/v1/customers/me/service-details")
    assert get_resp.status_code == 200
    assert get_resp.json()["serviceDetailsList"] == []


@pytest.mark.asyncio
async def test_delete_nonexistent_service_detail_404(customer_client):
    client, _ = customer_client
    resp = await client.delete(f"/api/v1/customers/me/service-details/{uuid4()}")
    assert resp.status_code == 404
