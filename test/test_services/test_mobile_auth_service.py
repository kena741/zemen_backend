"""Unit tests for MobileAuthService, pluggable SMS OTP, and session issuance."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.auth.hashing import hash_password, verify_password
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
    EntityNotFoundError,
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


@pytest.mark.asyncio
async def test_reset_password_by_phone_success(auth_service):
    service, sms_provider, _, (auth_repo, _, _, _) = auth_service
    user_id = uuid4()
    phone = "0911223344"

    auth_repo.get_by_phone.return_value = MobileUserCredentialsDomain(
        id=user_id,
        phone="+251911223344",
        hashed_password=hash_password("old_pass"),
        is_active=True,
    )

    v_id, code = await service.send_phone_otp(phone=phone)
    ok = await service.reset_password_by_phone(
        phone=phone,
        code=code,
        new_password="new_secure_password",
        verification_id=v_id,
    )
    assert ok is True
    auth_repo.update_password.assert_awaited_once()
    updated_uid, updated_hash = auth_repo.update_password.call_args.args
    assert updated_uid == user_id
    assert verify_password("new_secure_password", updated_hash)
    auth_repo.revoke_refresh_tokens.assert_awaited_once_with(user_id)


@pytest.mark.asyncio
async def test_reset_password_by_phone_invalid_otp_and_missing_user(auth_service):
    service, _, _, (auth_repo, _, _, _) = auth_service
    phone = "0911223344"
    v_id, code = await service.send_phone_otp(phone=phone)

    # Wrong OTP -> ValidationError, password is NOT updated
    with pytest.raises(ValidationError):
        await service.reset_password_by_phone(
            phone=phone,
            code="999999",
            new_password="new_secure_password",
            verification_id=v_id,
        )
    assert not auth_repo.update_password.called

    # Valid OTP but user not found -> EntityNotFoundError
    auth_repo.get_by_phone.return_value = None
    with pytest.raises(EntityNotFoundError):
        await service.reset_password_by_phone(
            phone=phone,
            code=code,
            new_password="new_secure_password",
            verification_id=v_id,
        )
    assert not auth_repo.update_password.called


@pytest.mark.asyncio
async def test_login_duplicate_phone_picks_matching_password_candidate(auth_service):
    service, _, _, (auth_repo, customer_repo, provider_repo, handyman_repo) = auth_service
    uid_1, uid_2 = uuid4(), uuid4()
    prov_2_id = uuid4()

    auth_repo.list_by_email_or_phone.return_value = [
        MobileUserCredentialsDomain(
            id=uid_1,
            email="hannah78@gmail.com",
            phone="+251951175959",
            hashed_password=hash_password("first_pass"),
            is_active=True,
        ),
        MobileUserCredentialsDomain(
            id=uid_2,
            email="hanna77@gmail.com",
            phone="+251951175959",
            hashed_password=hash_password("second_pass"),
            is_active=True,
        ),
    ]
    customer_repo.get_by_user_id.return_value = None
    provider_repo.get_by_user_id.return_value = ProviderDomain(
        id=prov_2_id,
        user_id=uid_2,
        first_name="Hana",
        last_name="Tame",
        phone_number="+251951175959",
    )
    handyman_repo.get_by_user_id.return_value = None

    session = await service.login("0951175959", "second_pass", expected_role="provider")
    assert session.user_id == uid_2
    assert session.provider_id == prov_2_id
    assert "provider" in session.roles


@pytest.mark.asyncio
async def test_signup_provider_attaches_to_existing_customer_user(auth_service):
    service, _, _, (auth_repo, customer_repo, provider_repo, _) = auth_service
    existing_uid = uuid4()
    existing_cust_id = uuid4()

    auth_repo.get_by_email.return_value = MobileUserCredentialsDomain(
        id=existing_uid,
        email="dual@example.com",
        phone="+251911223344",
        hashed_password=hash_password("shared_pass"),
        is_active=True,
    )
    customer_repo.get_by_user_id.return_value = CustomerDomain(
        id=existing_cust_id,
        user_id=existing_uid,
        first_name="Dual",
        last_name="User",
        phone="+251911223344",
    )
    provider_repo.get_by_user_id.return_value = None

    cmd = ProviderSignupDomain(
        email="dual@example.com",
        password="shared_pass",
        first_name="Dual",
        last_name="User",
        phone="0911223344",
    )
    session = await service.signup_provider(cmd)
    assert session.user_id == existing_uid
    assert session.provider_id is not None
    assert set(session.roles) == {"customer", "provider"}
    assert not auth_repo.create_user.called
    assert provider_repo.create_provider.called

