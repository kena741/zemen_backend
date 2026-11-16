"""Unit tests for WalletService."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.services.wallet_service import WalletService
from app.domain.customer import CustomerDomain
from app.domain.exceptions import ValidationError
from app.domain.finance import ProviderPaymentMethodDomain, WithdrawalDomain
from app.domain.provider import ProviderDomain


@pytest.fixture
def mock_wallet_tx_repo():
    repo = AsyncMock()
    repo.session = AsyncMock()
    repo.session.add = MagicMock()
    return repo


@pytest.fixture
def mock_withdrawal_repo():
    return AsyncMock()


@pytest.fixture
def mock_payment_method_repo():
    return AsyncMock()


@pytest.fixture
def mock_customer_repo():
    return AsyncMock()


@pytest.fixture
def mock_provider_repo():
    return AsyncMock()


@pytest.fixture
def wallet_service(
    mock_wallet_tx_repo,
    mock_withdrawal_repo,
    mock_payment_method_repo,
    mock_customer_repo,
    mock_provider_repo,
):
    return WalletService(
        wallet_tx_repo=mock_wallet_tx_repo,
        withdrawal_repo=mock_withdrawal_repo,
        payment_method_repo=mock_payment_method_repo,
        customer_repo=mock_customer_repo,
        provider_repo=mock_provider_repo,
    )


@pytest.mark.asyncio
async def test_get_balance(wallet_service, mock_customer_repo, mock_provider_repo):
    cust_id = uuid4()
    prov_id = uuid4()
    mock_customer_repo.get_by_id.return_value = CustomerDomain(
        id=cust_id,
        first_name="Abebe",
        last_name="Kebede",
        phone="+251911223344",
        wallet_amount=250.75,
    )
    mock_provider_repo.get_by_id.return_value = ProviderDomain(
        id=prov_id, user_id=uuid4(), wallet_amount="1420.50"
    )

    cust_bal = await wallet_service.get_balance(user_id=uuid4(), customer_id=cust_id)
    assert cust_bal == 250.75

    prov_bal = await wallet_service.get_balance(user_id=uuid4(), provider_id=prov_id)
    assert prov_bal == 1420.50


@pytest.mark.asyncio
async def test_request_withdrawal_success(
    wallet_service, mock_provider_repo, mock_withdrawal_repo, mock_wallet_tx_repo
):
    prov_id = uuid4()
    mock_provider_repo.get_by_id.return_value = ProviderDomain(
        id=prov_id, user_id=uuid4(), wallet_amount="2000.00"
    )
    mock_withdrawal_repo.create_withdrawal.return_value = WithdrawalDomain(
        id=uuid4(),
        provider_id=prov_id,
        amount=500.0,
        payment_status="pending",
    )

    withdrawal = await wallet_service.request_withdrawal(
        provider_id=prov_id, amount=500.0, note="Monthly payout"
    )
    assert withdrawal.amount == 500.0
    mock_provider_repo.update_provider.assert_awaited_once_with(
        provider_id=prov_id, values={"wallet_amount": "1500.0"}
    )
    mock_withdrawal_repo.create_withdrawal.assert_awaited_once()


@pytest.mark.asyncio
async def test_request_withdrawal_insufficient_balance(
    wallet_service, mock_provider_repo
):
    prov_id = uuid4()
    mock_provider_repo.get_by_id.return_value = ProviderDomain(
        id=prov_id, user_id=uuid4(), wallet_amount="100.00"
    )

    with pytest.raises(ValidationError, match="Insufficient wallet balance"):
        await wallet_service.request_withdrawal(provider_id=prov_id, amount=500.0)


@pytest.mark.asyncio
async def test_payment_methods_crud(
    wallet_service, mock_payment_method_repo
):
    prov_id = uuid4()
    mock_payment_method_repo.list_for_providers.return_value = [
        ProviderPaymentMethodDomain(
            id=uuid4(),
            provider_id=prov_id,
            bank_name="Commercial Bank of Ethiopia",
            account_number="1000123456789",
        )
    ]
    mock_payment_method_repo.upsert_payment_method.return_value = (
        ProviderPaymentMethodDomain(
            id=uuid4(),
            provider_id=prov_id,
            bank_name="Awash Bank",
            account_number="01412345678900",
        )
    )

    methods = await wallet_service.list_payment_methods(prov_id)
    assert len(methods) == 1

    created = await wallet_service.create_payment_method(
        prov_id,
        {"bankName": "Awash Bank", "accountNumber": "01412345678900"},
    )
    assert created.bank_name == "Awash Bank"
