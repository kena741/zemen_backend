"""Unit tests for MobileAuthService, pluggable SMS OTP, and session issuance."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.auth.hashing import hash_password
from app.core.sms.otp_engine import OtpEngine
from app.core.sms.provider import MockSMSProvider
from app.core.services.mobile_auth_service import MobileAuthService
from app.domain.auth import (
    CustomerSignupDomain,
    MobileUserCredentialsDomain,
    ProviderSignupDomain,
)
from app.domain.customer import CustomerDomain
from app.domain.exceptions import (
    AuthenticationError,
    EntityConflictError,
    ValidationError,
)
from app.domain.provider import ProviderDomain


@pytest.fixture
def mock_repos():
    auth_repo = AsyncMock()
    customer_repo = AsyncMock()
    provider_repo = AsyncMock()
    handyman_repo = AsyncMock()
    return auth_repo, customer_repo, provider_repo, handyman_repo


@pytest.fixture
def auth_service(mock_repos):
    auth_repo, customer_repo, provider_repo, handyman_repo = mock_repos
    sms_provider = MockSMSProvider()
    otp_engine = OtpEngine()
    service = MobileAuthService(
        auth_repo=auth_repo,
        customer_repo=customer_repo,
        provider_repo=provider_repo,
        handyman_repo=handyman_repo,
        sms_provider=sms_provider,
        otp_engine=otp_engine,
    )
    return service, sms_provider, otp_engine, mock_repos


@pytest.mark.asyncio
async def test_signup_customer_success(auth_service):
    service, _, _, (auth_repo, customer_repo, _, _) = auth_service
    auth_repo.get_by_email.return_value = None
    auth_repo.get_by_phone.return_value = None
    auth_repo.create_user.return_value = None
    auth_repo.store_refresh_token.return_value = None
    customer_repo.create_customer.return_value = None

    cmd = CustomerSignupDomain(
        email="john.doe@example.com",
        password="secretpassword",
        first_name="John",
        last_name="Doe",
        phone="+251911223344",
    )
    session = await service.signup_customer(cmd)

    assert session.access_token is not None
    assert session.customer_id is not None
    assert "customer" in session.roles
    assert auth_repo.create_user.called
    assert customer_repo.create_customer.called


@pytest.mark.asyncio
async def test_signup_customer_duplicate_email(auth_service):
    service, _, _, (auth_repo, _, _, _) = auth_service
    auth_repo.get_by_email.return_value = MobileUserCredentialsDomain(
        id=uuid4(), email="existing@example.com"
    )

    cmd = CustomerSignupDomain(
        email="existing@example.com",
        password="password123",
        first_name="Jane",
        last_name="Doe",
        phone="0911998877",
    )
    with pytest.raises(EntityConflictError):
        await service.signup_customer(cmd)


@pytest.mark.asyncio
async def test_pluggable_sms_otp_flow(auth_service):
    service, sms_provider, otp_engine, _ = auth_service
    phone = "0911223344"

    # 1. Send OTP
    v_id, plain_code = await service.send_phone_otp(phone=phone)
    assert len(plain_code) == 6
    assert len(sms_provider.dispatched_otps) == 1
    assert sms_provider.dispatched_otps[0]["recipient"] == "+251911223344"
    assert sms_provider.dispatched_otps[0]["code"] == plain_code

    # 2. Verify with wrong code -> fails
    with pytest.raises(ValidationError):
        await service.verify_phone_otp(phone=phone, code="000000", verification_id=v_id)

    # 3. Verify with correct code -> passes
    verified = await service.verify_phone_otp(phone=phone, code=plain_code, verification_id=v_id)
    assert verified is True


@pytest.mark.asyncio
async def test_login_success(auth_service):
    service, _, _, (auth_repo, customer_repo, provider_repo, handyman_repo) = auth_service
    user_id = uuid4()
    cust_id = uuid4()
    hashed = hash_password("correct_password")

    auth_repo.get_by_email_or_phone.return_value = MobileUserCredentialsDomain(
        id=user_id,
        email="test@example.com",
        hashed_password=hashed,
        is_active=True,
    )
    customer_repo.get_by_user_id.return_value = CustomerDomain(
        id=cust_id,
        user_id=user_id,
        first_name="Test",
        last_name="User",
        phone="+251911223344",
    )
    provider_repo.get_by_user_id.return_value = None
    handyman_repo.get_by_user_id.return_value = None

    session = await service.login("test@example.com", "correct_password")
    assert session.user_id == user_id
    assert session.customer_id == cust_id
    assert "customer" in session.roles


@pytest.mark.asyncio
async def test_login_invalid_password(auth_service):
    service, _, _, (auth_repo, _, _, _) = auth_service
    user_id = uuid4()
    hashed = hash_password("correct_password")

    auth_repo.get_by_email_or_phone.return_value = MobileUserCredentialsDomain(
        id=user_id,
        email="test@example.com",
        hashed_password=hashed,
        is_active=True,
    )

    with pytest.raises(AuthenticationError):
        await service.login("test@example.com", "wrong_password")

