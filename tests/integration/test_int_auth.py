"""
Integration tests: Auth endpoints.

Coverage
--------
POST   /api/v1/auth/signup/customer   — register customer
POST   /api/v1/auth/signup/provider   — register provider
POST   /api/v1/auth/login             — login with phone/password
GET    /api/v1/auth/me                — introspect token
POST   /api/v1/auth/logout            — revoke session
POST   /api/v1/auth/session/restore   — issue fresh tokens
DELETE /api/v1/auth/account           — soft-delete customer account
POST   /api/v1/auth/otp/send         — send OTP
"""

from __future__ import annotations

from uuid import uuid4

import pytest


# ============================================================
#  Customer signup
# ============================================================

@pytest.mark.asyncio
async def test_signup_customer_201(client):
    """Happy path: new customer → 201 with tokens and customer_id."""
    payload = {
        "phone": "+251922000001",
        "password": "SecurePass1!",
        "firstName": "Abebe",
        "lastName": "Kebede",
        "countryCode": "+251",
    }
    resp = await client.post("/api/v1/auth/signup/customer", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "accessToken" in body or "access_token" in body
    assert body.get("customerId") is not None or body.get("customer_id") is not None


@pytest.mark.asyncio
async def test_signup_customer_duplicate_phone_409(client):
    """Signing up with an already-registered phone returns 409."""
    payload = {
        "phone": "+251922000002",
        "password": "SecurePass1!",
        "firstName": "Test",
        "lastName": "User",
    }
    resp1 = await client.post("/api/v1/auth/signup/customer", json=payload)
    assert resp1.status_code == 201, resp1.text

    resp2 = await client.post("/api/v1/auth/signup/customer", json=payload)
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_signup_customer_missing_phone_422(client):
    """Missing required `phone` field → 422 Unprocessable Entity."""
    payload = {
        "password": "SecurePass1!",
        "firstName": "Test",
        "lastName": "User",
    }
    resp = await client.post("/api/v1/auth/signup/customer", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_signup_customer_missing_password_422(client):
    payload = {
        "phone": "+251922000003",
        "firstName": "Test",
        "lastName": "User",
    }
    resp = await client.post("/api/v1/auth/signup/customer", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_signup_customer_short_password_422(client):
    """Password shorter than 6 characters → 422."""
    payload = {
        "phone": "+251922000004",
        "password": "123",
        "firstName": "Test",
        "lastName": "User",
    }
    resp = await client.post("/api/v1/auth/signup/customer", json=payload)
    assert resp.status_code == 422


# ============================================================
#  Provider signup
# ============================================================

@pytest.mark.asyncio
async def test_signup_provider_201(client):
    """Happy path: new provider → 201 with tokens and provider_id."""
    payload = {
        "phone": "+251933000001",
        "password": "SecurePass1!",
        "firstName": "Dawit",
        "lastName": "Haile",
        "countryCode": "+251",
    }
    resp = await client.post("/api/v1/auth/signup/provider", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body.get("providerId") is not None or body.get("provider_id") is not None


# ============================================================
#  Login
# ============================================================

@pytest.mark.asyncio
async def test_login_success_200(client, seed_user):
    """Login with correct phone + password returns 200 and tokens."""
    phone = "+251944000001"
    password = "LoginPass1!"
    await seed_user(phone=phone, password=password)

    resp = await client.post(
        "/api/v1/auth/login",
        json={"phone": phone, "password": password},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "accessToken" in body or "access_token" in body


@pytest.mark.asyncio
async def test_login_wrong_password_401(client, seed_user):
    phone = "+251944000002"
    await seed_user(phone=phone, password="CorrectPass!")

    resp = await client.post(
        "/api/v1/auth/login",
        json={"phone": phone, "password": "WrongPass!"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_phone_401(client):
    """Non-existent phone returns 401 Unauthorized to prevent user enumeration."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"phone": "+251999999999", "password": "AnyPass1!"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_missing_identifier_422(client):
    """Login with neither phone nor email → 422."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"password": "SomePass1!"},
    )
    assert resp.status_code == 422


# ============================================================
#  GET /me
# ============================================================

@pytest.mark.asyncio
async def test_me_401_no_token(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_401_invalid_token(client):
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer totallyinvalidtoken"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_200_customer(customer_client):
    ac, cust = customer_client
    resp = await ac.get("/api/v1/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert "userId" in body or "user_id" in body
    assert "roles" in body
    roles = body["roles"]
    assert "customer" in roles


# ============================================================
#  Logout
# ============================================================

@pytest.mark.asyncio
async def test_logout_200(customer_client):
    ac, _ = customer_client
    resp = await ac.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("success") is True


@pytest.mark.asyncio
async def test_logout_requires_auth(client):
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 401


# ============================================================
#  Session restore
# ============================================================

@pytest.mark.asyncio
async def test_session_restore_200(customer_client):
    ac, _ = customer_client
    resp = await ac.post("/api/v1/auth/session/restore")
    assert resp.status_code == 200
    body = resp.json()
    assert "accessToken" in body or "access_token" in body


@pytest.mark.asyncio
async def test_session_restore_requires_auth(client):
    resp = await client.post("/api/v1/auth/session/restore")
    assert resp.status_code == 401


# ============================================================
#  Delete account
# ============================================================

@pytest.mark.asyncio
async def test_delete_account_200(customer_client):
    ac, _ = customer_client
    resp = await ac.delete("/api/v1/auth/account")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("success") is True


@pytest.mark.asyncio
async def test_delete_account_requires_customer_role(client, seed_provider):
    """A provider-only user (no customer profile) gets 403."""
    prov, user_id, _, token = await seed_provider(phone="+251955000001")
    resp = await client.delete(
        "/api/v1/auth/account",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Provider-only user has no customer profile → 403
    assert resp.status_code == 403


# ============================================================
#  OTP
# ============================================================

@pytest.mark.asyncio
async def test_send_otp_missing_recipient_422(client):
    resp = await client.post("/api/v1/auth/otp/send", json={})
    assert resp.status_code == 422
