"""Unit tests for ChapaPaymentService."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.services.chapa_payment_service import ChapaPaymentService
from app.domain.catalog import ServiceDomain
from app.domain.provider import ProviderDomain
from app.domain.settings import AppSettingDomain


@pytest.fixture
def mock_app_settings_repo():
    return AsyncMock()


@pytest.fixture
def mock_tax_repo():
    return AsyncMock()


@pytest.fixture
def mock_provider_repo():
    return AsyncMock()


@pytest.fixture
def mock_service_repo():
    return AsyncMock()


@pytest.fixture(autouse=True)
def mock_empty_chapa_secret_key(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "CHAPA_SECRET_KEY", "")


@pytest.fixture
def mock_chapa_http():
    http = AsyncMock()
    http.get = AsyncMock(
        return_value=(
            200,
            {
                "status": "success",
                "data": {
                    "status": "success",
                    "amount": 1000.0,
                    "currency": "ETB",
                    "tx_ref": "chapa_tx_activation_123",
                },
            },
        )
    )
    http.post = AsyncMock(
        return_value=(
            200,
            {
                "status": "success",
                "message": "Hosted Link",
                "data": {"checkout_url": "https://checkout.chapa.co/checkout/web/mock-session-123"},
            },
        )
    )
    return http


@pytest.fixture
def payment_service(
    mock_app_settings_repo, mock_tax_repo, mock_provider_repo, mock_service_repo, mock_chapa_http
):
    return ChapaPaymentService(
        app_settings_repo=mock_app_settings_repo,
        tax_repo=mock_tax_repo,
        provider_repo=mock_provider_repo,
        service_repo=mock_service_repo,
        chapa_http=mock_chapa_http,
    )


@pytest.mark.asyncio
async def test_get_payment_settings(payment_service, mock_app_settings_repo):
    mock_app_settings_repo.get_by_id.return_value = AppSettingDomain(
        id="payment",
        data={"chapa_public_key": "CHAPUBK_TEST-abc123xyz", "is_test": True},
    )

    settings = await payment_service.get_payment_settings()
    assert settings["chapaPublicKey"] == "CHAPUBK_TEST-abc123xyz"
    assert settings["isTest"] is True


@pytest.mark.asyncio
async def test_list_supported_banks_empty_when_no_credentials(
    mock_app_settings_repo, mock_tax_repo, mock_provider_repo, mock_service_repo
):
    from app.core.services.chapa_payment_service import clear_banks_cache, ChapaPaymentService

    clear_banks_cache()
    svc = ChapaPaymentService(
        app_settings_repo=mock_app_settings_repo,
        tax_repo=mock_tax_repo,
        provider_repo=mock_provider_repo,
        service_repo=mock_service_repo,
        chapa_http=None,
    )
    banks = await svc.list_supported_banks()
    assert banks == []


@pytest.mark.asyncio
async def test_verify_provider_activation(payment_service, mock_provider_repo):
    prov_id = uuid4()
    mock_provider_repo.get_by_id.return_value = ProviderDomain(
        id=prov_id,
        user_id=uuid4(),
        activation_paid=False,
    )

    res = await payment_service.verify_provider_activation(
        tx_ref="chapa_tx_activation_123",
        provider_id=prov_id,
        amount=500.0,
    )
    assert res["status"] == "success"
    assert res["activation_paid"] is True
    mock_provider_repo.update_provider.assert_awaited_once()

    # If already activated, returns idempotency response
    mock_provider_repo.get_by_id.return_value = ProviderDomain(
        id=prov_id,
        user_id=uuid4(),
        activation_paid=True,
    )
    res_again = await payment_service.verify_provider_activation(
        tx_ref="chapa_tx_activation_123",
        provider_id=prov_id,
        amount=500.0,
    )
    assert res_again["status"] == "already_activated"


@pytest.mark.asyncio
async def test_verify_service_tier_payment(payment_service, mock_provider_repo):
    prov_id = uuid4()
    mock_provider_repo.get_by_id.return_value = ProviderDomain(
        id=prov_id,
        user_id=uuid4(),
        service_tier_max=3,
    )

    res = await payment_service.verify_service_tier_payment(
        tx_ref="chapa_tx_tier_456",
        provider_id=prov_id,
        amount=1000.0,
        target_tier=10,
    )
    assert res["status"] == "success"
    assert res["service_tier_max"] == 10
    mock_provider_repo.update_provider.assert_awaited_once()


@pytest.mark.asyncio
async def test_verify_featured_request_payment(payment_service, mock_service_repo):
    prov_id = uuid4()
    srv_id = uuid4()
    mock_service_repo.get_by_id.return_value = ServiceDomain(
        id=srv_id,
        provider_id=prov_id,
        service_name="Painting",
        feature=False,
    )

    res = await payment_service.verify_featured_request_payment(
        tx_ref="chapa_tx_feat_789",
        provider_id=prov_id,
        service_id=srv_id,
        amount=250.0,
    )
    assert res["status"] == "success"
    assert res["feature"] is True
    mock_service_repo.update_service_fields.assert_awaited_once()


@pytest.mark.asyncio
async def test_initialize_payment_real_chapa(
    mock_app_settings_repo, mock_tax_repo, mock_provider_repo, mock_service_repo, monkeypatch
):
    from app.config import settings
    from app.core.services import chapa_client

    monkeypatch.setattr(settings, "CHAPA_SECRET_KEY", "CHASECK_TEST-123456789")

    mock_http = AsyncMock()
    mock_http.post = AsyncMock(
        return_value=(
            200,
            {
                "status": "success",
                "message": "Hosted Link",
                "data": {"checkout_url": "https://checkout.chapa.co/checkout/web/xyz123"},
            },
        )
    )

    service = ChapaPaymentService(
        app_settings_repo=mock_app_settings_repo,
        tax_repo=mock_tax_repo,
        provider_repo=mock_provider_repo,
        service_repo=mock_service_repo,
        chapa_http=mock_http,
    )

    init_res = await service.initialize_payment(
        amount=500.0,
        currency="ETB",
        email="provider@test.com",
        first_name="Abebe",
        last_name="Bikila",
        tx_ref="tx-test-init-001",
        callback_url="https://api.test.com/webhook",
        return_url="https://app.test.com/return",
    )

    assert init_res["status"] == "success"
    assert init_res["checkout_url"] == "https://checkout.chapa.co/checkout/web/xyz123"
    assert init_res["tx_ref"] == "tx-test-init-001"
    mock_http.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_verify_real_chapa_tx(
    mock_app_settings_repo, mock_tax_repo, mock_provider_repo, mock_service_repo, monkeypatch
):
    from app.config import settings

    monkeypatch.setattr(settings, "CHAPA_SECRET_KEY", "CHASECK_TEST-123456789")

    mock_http = AsyncMock()
    mock_http.get = AsyncMock(
        return_value=(
            200,
            {
                "status": "success",
                "message": "Payment details",
                "data": {
                    "status": "success",
                    "amount": 750.0,
                    "currency": "ETB",
                    "tx_ref": "tx-verify-real-001",
                },
            },
        )
    )

    service = ChapaPaymentService(
        app_settings_repo=mock_app_settings_repo,
        tax_repo=mock_tax_repo,
        provider_repo=mock_provider_repo,
        service_repo=mock_service_repo,
        chapa_http=mock_http,
    )

    res = await service.verify_chapa_tx(tx_ref="tx-verify-real-001", expected_amount=750.0)
    assert res["status"] == "success"
    assert res["amount"] == 750.0
    assert res["currency"] == "ETB"
    mock_http.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_supported_banks_from_chapa_api_and_caching(
    mock_app_settings_repo, mock_tax_repo, mock_provider_repo, mock_service_repo, monkeypatch
):
    import time
    from app.config import settings
    from app.core.services.chapa_payment_service import clear_banks_cache

    clear_banks_cache()
    monkeypatch.setattr(settings, "CHAPA_SECRET_KEY", "CHASECK_TEST-123456789")
    monkeypatch.setattr(settings, "CHAPA_BANKS_CACHE_TTL_SECONDS", 3600)

    mock_http = AsyncMock()
    mock_http.get = AsyncMock(
        return_value=(
            200,
            {
                "status": "success",
                "data": [
                    {
                        "id": "uuid-bank-cbe",
                        "bank_code": "853",
                        "name": "Commercial Bank of Ethiopia",
                        "acronym": "CBE",
                        "swift": "CBETETAA",
                        "acct_length": 13,
                        "is_rtgs": True,
                        "is_mobilemoney": False,
                    },
                    {
                        "id": "uuid-bank-telebirr",
                        "bank_code": "854",
                        "name": "Telebirr",
                        "acronym": "TELEBIRR",
                        "swift": "ETHTETAA",
                        "acct_length": 10,
                        "is_rtgs": False,
                        "is_mobilemoney": True,
                    },
                ],
            },
        )
    )

    service = ChapaPaymentService(
        app_settings_repo=mock_app_settings_repo,
        tax_repo=mock_tax_repo,
        provider_repo=mock_provider_repo,
        service_repo=mock_service_repo,
        chapa_http=mock_http,
    )

    # 1. First fetch -> calls API and caches with id set to bank_code
    banks = await service.list_supported_banks()
    assert len(banks) == 2
    assert banks[0]["id"] == "853"
    assert banks[0]["name"] == "Commercial Bank of Ethiopia"
    assert banks[0]["code"] == "CBE"
    assert banks[0]["swift"] == "CBETETAA"
    assert banks[0]["acct_length"] == 13
    assert banks[0]["is_rtgs"] is True
    assert banks[0]["is_mobilemoney"] is False

    assert banks[1]["id"] == "854"
    assert banks[1]["name"] == "Telebirr"
    assert banks[1]["code"] == "TELEBIRR"
    assert banks[1]["is_mobilemoney"] is True
    assert mock_http.get.await_count == 1

    # 2. Second fetch within TTL -> served from cache without HTTP call
    cached_banks = await service.list_supported_banks()
    assert cached_banks == banks
    assert mock_http.get.await_count == 1

    # 3. Force refresh -> bypasses cache and calls HTTP again
    refreshed_banks = await service.list_supported_banks(force_refresh=True)
    assert refreshed_banks == banks
    assert mock_http.get.await_count == 2

    # 4. TTL expiration -> advance clock past TTL and verify re-fetch
    current_time = time.time()
    monkeypatch.setattr(time, "time", lambda: current_time + 4000)
    expired_banks = await service.list_supported_banks()
    assert expired_banks == banks
    assert mock_http.get.await_count == 3

    # 5. Fallback on network/API error -> returns cached banks
    mock_http.get.side_effect = RuntimeError("Chapa API network timeout")
    fallback_banks = await service.list_supported_banks(force_refresh=True)
    assert fallback_banks == banks


def test_chapa_webhook_signature_verification():
    import hashlib
    import hmac

    from app.core.services import chapa_client

    payload = b'{"event":"charge.complete","tx_ref":"tx-123"}'
    secret = "test-secret-key"
    valid_sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    assert chapa_client.verify_webhook_signature(payload, valid_sig, secret=secret) is True
    assert chapa_client.verify_webhook_signature(payload, "invalid_sig", secret=secret) is False
    assert chapa_client.verify_webhook_signature(payload, None, secret=secret) is False


def test_chapa_bank_model_parsing():
    from app.core.services.chapa_client import ChapaBank

    # Full data payload
    raw_bank = {
        "id": "uuid-999",
        "bank_code": "855",
        "name": "Awash Bank",
        "acronym": "AWASH",
        "swift": "AWINETAA",
        "acct_length": 14,
        "is_rtgs": True,
        "is_mobilemoney": False,
    }
    bank = ChapaBank.from_api_dict(raw_bank)
    assert bank.id == "855"
    assert bank.name == "Awash Bank"
    assert bank.code == "AWASH"
    assert bank.swift == "AWINETAA"
    assert bank.acct_length == 14
    assert bank.is_rtgs is True
    assert bank.is_mobilemoney is False
    # Dict access compatibility
    assert bank["id"] == "855"
    assert bank.get("swift") == "AWINETAA"
    assert bank.to_dict()["id"] == "855"

    # Minimal payload fallback (no bank_code, falls back to id)
    minimal_raw = {"id": "860", "name": "Cooperative Bank"}
    min_bank = ChapaBank.from_api_dict(minimal_raw)
    assert min_bank.id == "860"
    assert min_bank.code == "860"
    assert min_bank.swift is None
    assert min_bank.acct_length is None


@pytest.mark.asyncio
async def test_list_subscription_plans(payment_service, mock_provider_repo):
    from decimal import Decimal
    from unittest.mock import MagicMock
    from app.persistence.sqlalchemy.models.finance import Subscription

    mock_sub = Subscription(
        id=1,
        title="Starter Plan",
        description="Up to 2 services",
        price=Decimal("500.00"),
        service_limit=2,
        duration="1 Month",
        plan_type="tier",
        active=True,
    )
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [mock_sub]
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_provider_repo.session = mock_session

    plans = await payment_service.list_subscription_plans()
    assert len(plans) == 1
    assert plans[0]["id"] == 1
    assert plans[0]["service_limit"] == 2
    assert plans[0]["price"] == 500.0


@pytest.mark.asyncio
async def test_initiate_tier_purchase(payment_service, mock_provider_repo):
    from decimal import Decimal
    from unittest.mock import MagicMock
    from app.persistence.sqlalchemy.models.finance import Subscription

    prov_id = uuid4()
    mock_provider_repo.get_by_id.return_value = ProviderDomain(
        id=prov_id,
        user_id=uuid4(),
        email="provider@test.com",
        first_name="Abebe",
        last_name="Bikila",
    )
    mock_sub = Subscription(
        id=1,
        title="Starter Plan",
        description="Up to 2 services",
        price=Decimal("500.00"),
        service_limit=2,
        duration="1 Month",
        plan_type="tier",
        active=True,
    )
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [mock_sub]
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_provider_repo.session = mock_session

    res = await payment_service.initiate_tier_purchase(
        provider_id=prov_id,
        plan_id=1,
    )

    assert res["status"] == "success"
    assert "checkout_url" in res
    assert res["tx_ref"].startswith(f"tier-{prov_id.hex[:6]}-")
    mock_provider_repo.update_provider.assert_awaited_once()


