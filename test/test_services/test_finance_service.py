"""Unit tests for FinanceAdminService."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.security.admin_deps import AdminContext
from app.core.services.admin.audit_service import AdminAuditService
from app.core.services.admin.finance_service import FinanceAdminService
from app.domain.finance import (
    CountryTaxDomain,
    ProviderPaymentMethodDomain,
    WithdrawalDomain,
)
from app.domain.provider import ProviderDomain
from app.persistence.repositories.activity_log_repo import ActivityLogRepository
from app.persistence.repositories.provider_payment_method_repo import ProviderPaymentMethodRepository
from app.persistence.repositories.provider_repo import ProviderRepository
from app.persistence.repositories.tax_repo import CountryTaxRepository
from app.persistence.repositories.wallet_transaction_repo import WalletTransactionRepository
from app.persistence.repositories.withdrawal_repo import WithdrawalRepository
from .conftest import ServiceMockSession


@pytest.fixture
def mock_context() -> AdminContext:
    return AdminContext(
        admin_id=uuid4(),
        user_id=uuid4(),
        email="superadmin@lolelink.com",
        full_name="Super Admin",
        role="super_admin",
        permissions=["*"],
    )


@pytest.fixture
def finance_service():
    session = ServiceMockSession()
    w_repo = WithdrawalRepository(session)  # type: ignore[arg-type]
    p_repo = ProviderRepository(session)  # type: ignore[arg-type]
    m_repo = ProviderPaymentMethodRepository(session)  # type: ignore[arg-type]
    wt_repo = WalletTransactionRepository(session)  # type: ignore[arg-type]
    t_repo = CountryTaxRepository(session)  # type: ignore[arg-type]
    audit_repo = ActivityLogRepository(session)  # type: ignore[arg-type]
    audit_service = AdminAuditService(audit_repo)

    fcm_mock = MagicMock()
    fcm_mock.send_to_token = AsyncMock(return_value={"sent": True, "message_id": "msg-finance-123"})

    service = FinanceAdminService(
        withdrawal_repo=w_repo,
        provider_repo=p_repo,
        payment_method_repo=m_repo,
        wallet_repo=wt_repo,
        tax_repo=t_repo,
        audit_service=audit_service,
        fcm_service=fcm_mock,
    )
    return service, w_repo, p_repo, m_repo, t_repo, fcm_mock, session


@pytest.mark.asyncio
async def test_review_withdrawal_approve(finance_service, mock_context):
    service, w_repo, p_repo, _, _, fcm_mock, session = finance_service
    w_id = uuid4()
    prov_id = uuid4()

    w_pending = WithdrawalDomain(
        id=w_id,
        provider_id=prov_id,
        amount=1500.0,
        payment_status="pending",
        bank_name="Awash Bank",
        account_number="0132000000000",
    )
    w_approved = WithdrawalDomain(
        id=w_id,
        provider_id=prov_id,
        amount=1500.0,
        payment_status="approved",
        bank_name="Awash Bank",
        account_number="0132000000000",
    )

    w_repo.get_by_id_enriched = AsyncMock(side_effect=[w_pending, w_approved])
    w_repo.update_status = AsyncMock(return_value=True)

    p_repo.get_by_id = AsyncMock(
        return_value=ProviderDomain(
            id=prov_id,
            user_id=uuid4(),
            first_name="Sara",
            last_name="Mohammed",
            fcm_token="prov_fcm_token_789",
        )
    )

    res = await service.review_withdrawal(
        withdrawal_id=w_id,
        action="approve",
        admin_note="Approved by finance manager",
        ctx=mock_context,
    )

    assert res.id == w_id
    assert res.payment_status == "approved"
    fcm_mock.send_to_token.assert_called_once()


@pytest.mark.asyncio
async def test_review_withdrawal_conflict_when_not_pending(finance_service, mock_context):
    service, w_repo, _, _, _, _, _ = finance_service
    w_id = uuid4()

    w_completed = WithdrawalDomain(
        id=w_id,
        provider_id=uuid4(),
        amount=1500.0,
        payment_status="completed",
    )
    w_repo.get_by_id_enriched = AsyncMock(return_value=w_completed)

    with pytest.raises(HTTPException) as exc_info:
        await service.review_withdrawal(
            withdrawal_id=w_id,
            action="approve",
            ctx=mock_context,
        )

    assert exc_info.value.status_code == 409
    assert "already completed" in exc_info.value.detail


@pytest.mark.asyncio
async def test_complete_withdrawal_deducts_provider_wallet(finance_service, mock_context):
    service, w_repo, p_repo, _, _, fcm_mock, session = finance_service
    w_id = uuid4()
    prov_id = uuid4()

    w_approved = WithdrawalDomain(
        id=w_id,
        provider_id=prov_id,
        amount=2000.0,
        payment_status="approved",
        bank_name="Dashen Bank",
        account_number="500012345678",
    )
    w_completed = WithdrawalDomain(
        id=w_id,
        provider_id=prov_id,
        amount=2000.0,
        payment_status="completed",
        bank_name="Dashen Bank",
        account_number="500012345678",
    )

    w_repo.get_by_id_enriched = AsyncMock(side_effect=[w_approved, w_completed])
    w_repo.mark_completed = AsyncMock(return_value=True)

    p_repo.get_by_id = AsyncMock(
        return_value=ProviderDomain(
            id=prov_id,
            user_id=uuid4(),
            first_name="Tadesse",
            last_name="Girma",
            wallet_amount=Decimal("3500.00"),
            fcm_token="tadesse_token",
        )
    )
    p_repo.update = AsyncMock(return_value=True)

    res = await service.complete_withdrawal(
        withdrawal_id=w_id,
        admin_note="Transferred via online banking",
        ctx=mock_context,
    )

    assert res.payment_status == "completed"
    p_repo.update.assert_called_once_with(prov_id, {"wallet_amount": Decimal("1500.0")})
    assert len(session.added) >= 1  # WalletTransaction created
    fcm_mock.send_to_token.assert_called_once()


@pytest.mark.asyncio
async def test_chapa_transfer_success(finance_service, mock_context):
    service, w_repo, _, m_repo, _, _, session = finance_service
    w_id = uuid4()
    prov_id = uuid4()

    w_approved = WithdrawalDomain(
        id=w_id,
        provider_id=prov_id,
        amount=1000.0,
        payment_status="approved",
        bank_name="CBE",
        account_number="1000111222333",
    )
    w_repo.get_by_id_enriched = AsyncMock(return_value=w_approved)
    w_repo.update_status = AsyncMock(return_value=True)

    m_repo.get_default_for_provider = AsyncMock(
        return_value=ProviderPaymentMethodDomain(
            id=uuid4(),
            provider_id=prov_id,
            bank_name="CBE",
            account_number="1000111222333",
            holder_name="Provider CBE",
        )
    )

    res = await service.chapa_transfer(withdrawal_id=w_id, ctx=mock_context)
    assert res["amount"] == 1000.0
    assert res["chapa_fee"] == 10.0
    assert res["net_transfer_amount"] == 990.0
    assert "payout-" in res["tx_ref"]


@pytest.mark.asyncio
async def test_export_audit_csv(finance_service):
    service, w_repo, _, _, _, _, _ = finance_service
    w_id = uuid4()
    w = WithdrawalDomain(
        id=w_id,
        provider_id=uuid4(),
        amount=1200.0,
        payment_status="completed",
        bank_name="Bank of Abyssinia",
        account_number="9988776655",
        provider_name="Abyssinia Cleaners",
    )
    w_repo.list_withdrawals = AsyncMock(return_value=[w])

    csv_data = await service.export_audit_csv()
    assert "id,created_date,provider_id" in csv_data
    assert "Abyssinia Cleaners" in csv_data
    assert "1200.0" in csv_data


@pytest.mark.asyncio
async def test_country_tax_crud(finance_service, mock_context):
    service, _, _, _, t_repo, _, _ = finance_service
    tax_domain = CountryTaxDomain(
        id=1,
        name="Turnover Tax",
        country="Ethiopia",
        value=2.0,
        type="percentage",
        is_fix=False,
        active=True,
    )
    t_repo.create = AsyncMock(return_value=MagicMock())
    t_repo.to_domain = MagicMock(return_value=tax_domain)
    t_repo.get_by_id = AsyncMock(return_value=tax_domain)
    t_repo.update = AsyncMock(return_value=True)
    t_repo.delete = AsyncMock(return_value=True)

    created = await service.create_tax(
        name="Turnover Tax",
        country="Ethiopia",
        value=2.0,
        ctx=mock_context,
    )
    assert created.id == 1
    assert created.name == "Turnover Tax"

    await service.delete_tax(tax_id=1, ctx=mock_context)
    t_repo.delete.assert_called_once_with(1)

