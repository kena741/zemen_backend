"""Integration tests for Mobile Authentication and Pluggable SMS OTP endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routers.auth import get_mobile_auth_service
from app.core.security.deps import AuthContext
from app.domain.auth import AuthSessionDomain
from app.domain.exceptions import AuthenticationError, EntityConflictError, ValidationError


@pytest.fixture
def mock_auth_service():
    service = AsyncMock()
    return service


def test_signup_customer_api(api_client, mock_auth_service):
    user_id = uuid4()
    cust_id = uuid4()
    mock_auth_service.signup_customer.return_value = AuthSessionDomain(
        user_id=user_id,
        access_token="mock_access_token",
        refresh_token="mock_refresh_token",
        roles=["customer"],
        customer_id=cust_id,
        user={"id": str(user_id), "email": "test@example.com"},
    )

    client = api_client()
    client.app.dependency_overrides[get_mobile_auth_service] = lambda: mock_auth_service

    payload = {
        "email": "test@example.com",
        "password": "mypassword123",
        "first_name": "Abebe",
        "last_name": "Bikila",
        "phone": "+251911223344",
    }
    response = client.post("/api/v1/auth/signup/customer", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "accessToken" in data or "access_token" in data
    assert data["roles"] == ["customer"]


def test_login_api_success(api_client, mock_auth_service):
    user_id = uuid4()
    mock_auth_service.login.return_value = AuthSessionDomain(
        user_id=user_id,
        access_token="mock_access_token",
        refresh_token="mock_refresh_token",
        roles=["customer"],
        customer_id=uuid4(),
        user={"id": str(user_id)},
    )

    client = api_client()
    client.app.dependency_overrides[get_mobile_auth_service] = lambda: mock_auth_service

    payload = {
        "identifier": "0911223344",
        "password": "valid_password",
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["roles"] == ["customer"]


def test_login_api_failure(api_client, mock_auth_service):
    mock_auth_service.login.side_effect = AuthenticationError("Invalid login credentials.")

    client = api_client()
    client.app.dependency_overrides[get_mobile_auth_service] = lambda: mock_auth_service

    payload = {
        "identifier": "0911223344",
        "password": "wrong_password",
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    assert "Invalid login credentials" in response.json()["message"]


def test_send_otp_endpoints(api_client, mock_auth_service):
    v_id = str(uuid4())
    mock_auth_service.send_phone_otp.return_value = (v_id, "123456")

    client = api_client()
    client.app.dependency_overrides[get_mobile_auth_service] = lambda: mock_auth_service

    # Test /api/v1/auth/otp/send
    res1 = client.post("/api/v1/auth/otp/send", json={"phone": "0911223344"})
    assert res1.status_code == 200
    assert res1.json()["success"] is True

    # Test compatibility /sms/send-otp
    res2 = client.post("/sms/send-otp", json={"recipient": "0911223344"})
    assert res2.status_code == 200
    assert res2.json()["success"] is True


def test_verify_otp_endpoints(api_client, mock_auth_service):
    mock_auth_service.verify_phone_otp.return_value = True

    client = api_client()
    client.app.dependency_overrides[get_mobile_auth_service] = lambda: mock_auth_service

    res = client.post("/sms/verify-otp", json={"recipient": "0911223344", "code": "123456"})
    assert res.status_code == 200
    assert res.json()["success"] is True


def test_auth_me_introspection(api_client):
    user_id = uuid4()
    cust_id = uuid4()
    context = AuthContext(
        user_id=user_id,
        email="user@example.com",
        roles=["customer"],
        customer_id=cust_id,
    )

    client = api_client(auth_context=context)
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 200
    data = res.json()
    assert data["userId"] == str(user_id) or data["user_id"] == str(user_id)
    assert data["roles"] == ["customer"]


def test_logout_endpoint(api_client, mock_auth_service):
    mock_auth_service.logout.return_value = None

    context = AuthContext(
        user_id=uuid4(),
        email="user@example.com",
        roles=["customer"],
    )
    client = api_client(auth_context=context)
    client.app.dependency_overrides[get_mobile_auth_service] = lambda: mock_auth_service

    res = client.post("/api/v1/auth/logout")
    assert res.status_code == 200
    assert res.json()["success"] is True

