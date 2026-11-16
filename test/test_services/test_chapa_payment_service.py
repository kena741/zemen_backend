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


@pytest.fixture
def payment_service(
    mock_app_settings_repo, mock_tax_repo, mock_provider_repo, mock_service_repo
):
    return ChapaPaymentService(
        app_settings_repo=mock_app_settings_repo,
        tax_repo=mock_tax_repo,
        provider_repo=mock_provider_repo,
        service_repo=mock_service_repo,
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
async def test_list_supported_banks(payment_service):
    banks = await payment_service.list_supported_banks()
    assert len(banks) > 5
    assert any(b["code"] == "CBE" for b in banks)
    assert any(b["code"] == "TELEBIRR" for b in banks)


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
