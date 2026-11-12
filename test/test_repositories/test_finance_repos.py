"""Unit and mapping tests for Finance repositories."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.persistence.repositories.provider_payment_method_repo import ProviderPaymentMethodRepository
from app.persistence.repositories.tax_repo import CountryTaxRepository
from app.persistence.repositories.wallet_transaction_repo import WalletTransactionRepository
from app.persistence.repositories.withdrawal_repo import WithdrawalRepository
from app.persistence.sqlalchemy.models.config import CountryTax
from app.persistence.sqlalchemy.models.finance import (
    ProviderPaymentMethod,
    WalletTransaction,
    WithdrawalHistory,
)
from .conftest import RepoMockSession


@pytest.mark.asyncio
async def test_withdrawal_repo_to_domain():
    w_id = uuid4()
    prov_id = uuid4()
    entity = WithdrawalHistory(
        id=w_id,
        provider_id=prov_id,
        amount="2500.00",
        payment_status="pending",
        bank_name="Commercial Bank of Ethiopia",
        account_number="1000123456789",
        holder_name="Almaz Kebede",
        created_date=datetime.now(timezone.utc),
    )

    session = RepoMockSession(scalar_one_or_none_value=entity)
    repo = WithdrawalRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(
        entity,
        provider_name="Almaz Kebede",
        provider_phone="+251911223344",
        provider_email="almaz@example.com",
    )

    assert domain.id == w_id
    assert domain.provider_id == prov_id
    assert domain.amount == 2500.0
    assert domain.payment_status == "pending"
    assert domain.bank_name == "Commercial Bank of Ethiopia"
    assert domain.account_number == "1000123456789"
    assert domain.provider_name == "Almaz Kebede"


@pytest.mark.asyncio
async def test_provider_payment_method_repo_to_domain():
    method_id = uuid4()
    prov_id = uuid4()
    entity = ProviderPaymentMethod(
        id=method_id,
        provider_id=prov_id,
        method_type="bank",
        method_code="cbe",
        method_name="Commercial Bank of Ethiopia",
        bank_name="CBE",
        account_number="1000987654321",
        holder_name="Dawit Haile",
        is_active=True,
        is_default=True,
        currency="ETB",
    )

    session = RepoMockSession(scalar_one_or_none_value=entity)
    repo = ProviderPaymentMethodRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(entity)
    assert domain.id == method_id
    assert domain.provider_id == prov_id
    assert domain.account_number == "1000987654321"
    assert domain.is_default is True
    assert domain.currency == "ETB"


@pytest.mark.asyncio
async def test_wallet_transaction_repo_to_domain():
    tx_id = uuid4()
    user_id = uuid4()
    entity = WalletTransaction(
        id=tx_id,
        user_id=user_id,
        amount="500.00",
        is_credit=True,
        payment_type="payout",
        type="booking_payout",
        note="Payout for completed booking",
        created_date=datetime.now(timezone.utc),
    )

    session = RepoMockSession(scalar_one_or_none_value=entity)
    repo = WalletTransactionRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(
        entity,
        user_full_name="Abebe Bikila",
        user_email="abebe@example.com",
    )
    assert domain.id == tx_id
    assert domain.amount == "500.00"
    assert domain.is_credit is True
    assert domain.user_full_name == "Abebe Bikila"


@pytest.mark.asyncio
async def test_country_tax_repo_to_domain():
    entity = CountryTax(
        id=1,
        name="Value Added Tax",
        country="Ethiopia",
        value=Decimal("15.00"),
        type="percentage",
        is_fix=False,
        active=True,
        created_at=datetime.now(timezone.utc),
    )

    session = RepoMockSession(scalar_one_or_none_value=entity)
    repo = CountryTaxRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(entity)
    assert domain.id == 1
    assert domain.name == "Value Added Tax"
    assert domain.value == 15.0
    assert domain.is_fix is False
    assert domain.active is True

