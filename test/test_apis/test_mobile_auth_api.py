"""Integration tests for Mobile Authentication and Pluggable SMS OTP endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routers.auth import get_mobile_auth_service
from app.core.auth.hashing import hash_password, verify_password
from app.core.security.deps import AuthContext
from app.core.services.mobile_auth_service import MobileAuthService
from app.core.sms.otp_engine import OtpEngine
from app.core.sms.provider import MockSMSProvider
from app.domain.auth import AuthSessionDomain, MobileUserCredentialsDomain
from app.domain.customer import CustomerDomain
from app.domain.exceptions import AuthenticationError, EntityConflictError, ValidationError
from app.domain.provider import ProviderDomain


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
        "phone": "0911223344",
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
        "phone": "0911223344",
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


def test_forgot_password_workflow_integration(api_client):
    """End-to-end forgot-password workflow: check-phone -> send OTP -> reset -> login role check."""
    user_id = uuid4()
    cust_id = uuid4()
    phone = "+251911223344"

    # In-memory user state backed by real MobileAuthService, OtpEngine, and MockSMSProvider
    user_record = MobileUserCredentialsDomain(
        id=user_id,
        email="customer@example.com",
        phone=phone,
        hashed_password=hash_password("OldPassword123"),
        is_active=True,
    )

    auth_repo = AsyncMock()
    auth_repo.get_by_phone.side_effect = lambda p: user_record if p in {phone, "0911223344"} else None
    auth_repo.get_by_email_or_phone.side_effect = lambda i: user_record if i in {phone, "0911223344", "customer@example.com"} else None

    async def _update_password(uid, new_hash):
        assert uid == user_id
        user_record.hashed_password = new_hash

    auth_repo.update_password.side_effect = _update_password
    auth_repo.revoke_refresh_tokens.return_value = None
    auth_repo.record_sign_in.return_value = None
    auth_repo.store_refresh_token.return_value = None

    customer_repo = AsyncMock()
    customer_repo.get_by_user_id.return_value = CustomerDomain(
        id=cust_id,
        user_id=user_id,
        first_name="Abebe",
        last_name="Bikila",
        phone=phone,
    )
    provider_repo = AsyncMock()
    provider_repo.get_by_user_id.return_value = None
    handyman_repo = AsyncMock()
    handyman_repo.get_by_user_id.return_value = None

    sms_provider = MockSMSProvider()
    otp_engine = OtpEngine()
    real_service = MobileAuthService(
        auth_repo=auth_repo,
        customer_repo=customer_repo,
        provider_repo=provider_repo,
        handyman_repo=handyman_repo,
        sms_provider=sms_provider,
        otp_engine=otp_engine,
    )

    client = api_client()
    client.app.dependency_overrides[get_mobile_auth_service] = lambda: real_service

    # Step 1: Check unregistered phone -> 404
    res_unknown = client.post("/api/v1/auth/password/reset/check-phone", json={"phone": "0999887766"})
    assert res_unknown.status_code == 404

    # Step 1b: Check registered phone -> 200
    res_check = client.post("/api/v1/auth/password/reset/check-phone", json={"phone": "0911223344"})
    assert res_check.status_code == 200
    assert res_check.json()["success"] is True

    # Step 2: Send OTP via SMS
    res_otp = client.post("/api/v1/auth/otp/send", json={"phone": "0911223344"})
    assert res_otp.status_code == 200
    verification_id = res_otp.json()["verificationId"] if "verificationId" in res_otp.json() else res_otp.json()["verification_id"]
    assert len(sms_provider.dispatched_otps) == 1
    otp_code = sms_provider.dispatched_otps[0]["code"]

    # Step 3a: Wrong OTP -> 422
    res_bad_otp = client.post(
        "/api/v1/auth/password/reset/phone",
        json={
            "phone": "0911223344",
            "code": "000000",
            "new_password": "NewPassword456",
            "verification_id": verification_id,
        },
    )
    assert res_bad_otp.status_code == 422

    # Step 3b: Valid OTP -> 200, password updated & refresh tokens revoked
    res_reset = client.post(
        "/api/v1/auth/password/reset/phone",
        json={
            "phone": "0911223344",
            "code": otp_code,
            "new_password": "NewPassword456",
            "verification_id": verification_id,
        },
    )
    assert res_reset.status_code == 200
    assert res_reset.json()["success"] is True
    assert auth_repo.revoke_refresh_tokens.called
    assert verify_password("NewPassword456", user_record.hashed_password)

    # Step 4a: Old password no longer works
    res_old_login = client.post(
        "/api/v1/auth/login/customer",
        json={"phone": "0911223344", "password": "OldPassword123"},
    )
    assert res_old_login.status_code == 401

    # Step 4b: New password works on Customer App login
    res_cust_login = client.post(
        "/api/v1/auth/login/customer",
        json={"phone": "0911223344", "password": "NewPassword456"},
    )
    assert res_cust_login.status_code == 200
    assert res_cust_login.json()["roles"] == ["customer"]

    # Step 4c: Same user cannot log into Provider App (role distinction enforced)
    res_prov_login = client.post(
        "/api/v1/auth/login/provider",
        json={"phone": "0911223344", "password": "NewPassword456"},
    )
    assert res_prov_login.status_code == 401

