"""Integration tests for Admin Finance and Payouts API endpoints."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.security.admin_deps import AdminContext
from app.domain.finance import (
    ChapaBalanceDomain,
    CountryTaxDomain,
    EnrichedWalletTransactionDomain,
    ProviderPayoutAnalysisDomain,
    WithdrawalDomain,
)
from .conftest import ApiTestDbSession


@pytest.fixture
def super_admin_context() -> AdminContext:
    return AdminContext(
        admin_id=uuid4(),
        user_id=uuid4(),
        email="superadmin@lolelink.com",
        full_name="Super Admin",
        role="super_admin",
        permissions=["*"],
    )


def test_list_payouts_endpoint(api_client, super_admin_context):
    w_id = uuid4()
    prov_id = uuid4()
    mock_w = WithdrawalDomain(
        id=w_id,
        provider_id=prov_id,
        amount=3500.0,
        payment_status="pending",
        bank_name="Commercial Bank of Ethiopia",
        account_number="100012345678",
        holder_name="Solomon Desta",
        provider_name="Solomon Desta",
        created_date=datetime.now(timezone.utc),
    )

    with patch("app.api.v1.routers.admin.finance._get_finance_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.list_withdrawals = AsyncMock(return_value=[mock_w])

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.get("/api/v1/admin/finance/payouts")

        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == str(w_id)
        assert data[0]["amount"] == 3500.0
        assert data[0]["paymentStatus"] == "pending"
        assert data[0]["providerName"] == "Solomon Desta"
        assert data[0]["accountNumber"] == "100012345678"


def test_get_finance_badge_count(api_client, super_admin_context):
    with patch("app.api.v1.routers.admin.finance._get_finance_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.count_badge = AsyncMock(return_value=12)

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.get("/api/v1/admin/finance/badge-count")

        assert res.status_code == 200
        assert res.json() == {"count": 12}


def test_review_payout_endpoint(api_client, super_admin_context):
    w_id = uuid4()
    mock_w = WithdrawalDomain(
        id=w_id,
        provider_id=uuid4(),
        amount=1200.0,
        payment_status="approved",
        admin_note="Approved for transfer",
    )

    with patch("app.api.v1.routers.admin.finance._get_finance_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.review_withdrawal = AsyncMock(return_value=mock_w)

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.post(
            "/api/v1/admin/finance/payouts/review",
            json={
                "withdrawalId": str(w_id),
                "action": "approve",
                "adminNote": "Approved for transfer",
            },
        )

        assert res.status_code == 200
        data = res.json()["data"]
        assert data["id"] == str(w_id)
        assert data["paymentStatus"] == "approved"
        assert data["adminNote"] == "Approved for transfer"


def test_complete_payout_endpoint(api_client, super_admin_context):
    w_id = uuid4()
    mock_w = WithdrawalDomain(
        id=w_id,
        provider_id=uuid4(),
        amount=2500.0,
        payment_status="completed",
        payment_date="2026-11-12T10:00:00Z",
    )

    with patch("app.api.v1.routers.admin.finance._get_finance_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.complete_withdrawal = AsyncMock(return_value=mock_w)

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.post(
            "/api/v1/admin/finance/payouts/complete",
            json={"withdrawalId": str(w_id), "adminNote": "Bank transfer completed"},
        )

        assert res.status_code == 200
        data = res.json()["data"]
        assert data["id"] == str(w_id)
        assert data["paymentStatus"] == "completed"


def test_chapa_transfer_endpoint(api_client, super_admin_context):
    w_id = uuid4()

    with patch("app.api.v1.routers.admin.finance._get_finance_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.chapa_transfer = AsyncMock(
            return_value={
                "tx_ref": "payout-12345678-abcd",
                "transfer_id": "tr-987",
                "amount": 1000.0,
                "net_transfer_amount": 990.0,
            }
        )

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.post(
            "/api/v1/admin/finance/payouts/chapa-transfer",
            json={"withdrawalId": str(w_id)},
        )

        assert res.status_code == 200
        body = res.json()
        assert body["tx_ref"] == "payout-12345678-abcd"
        assert body["amount"] == 1000.0


def test_provider_wallet_analysis_endpoint(api_client, super_admin_context):
    prov_id = uuid4()
    analysis = ProviderPayoutAnalysisDomain(
        provider_id=prov_id,
        current_wallet_balance=4500.0,
        total_earned=12000.0,
        total_completed_payouts=7500.0,
        pending_payout_amount=1500.0,
        total_commission_paid=1200.0,
        booking_count=18,
        completed_booking_count=15,
    )

    with patch("app.api.v1.routers.admin.finance._get_finance_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.analyze_provider_wallet = AsyncMock(return_value=analysis)

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.get(f"/api/v1/admin/finance/provider-wallet-analysis?providerId={prov_id}")

        assert res.status_code == 200
        body = res.json()
        assert body["providerId"] == str(prov_id)
        assert body["currentWalletBalance"] == 4500.0
        assert body["totalEarned"] == 12000.0
        assert body["bookingCount"] == 18


def test_wallet_transactions_endpoint(api_client, super_admin_context):
    tx_id = uuid4()
    mock_tx = EnrichedWalletTransactionDomain(
        id=tx_id,
        amount="400.00",
        is_credit=True,
        payment_type="payout",
        type="booking_payout",
        user_id=uuid4(),
        provider_id=uuid4(),
        customer_id=None,
        user_full_name="Martha Kebede",
        created_date=datetime.now(timezone.utc),
    )

    with patch("app.api.v1.routers.admin.finance._get_finance_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.list_wallet_transactions = AsyncMock(return_value=[mock_tx])

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.get("/api/v1/admin/finance/wallet-transactions")

        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == str(tx_id)
        assert data[0]["isCredit"] is True
        assert data[0]["userFullName"] == "Martha Kebede"


def test_taxes_crud_endpoints(api_client, super_admin_context):
    tax_1 = CountryTaxDomain(
        id=1,
        name="Value Added Tax",
        country="Ethiopia",
        value=15.0,
        type="percentage",
        is_fix=False,
        active=True,
    )

    with patch("app.api.v1.routers.admin.finance._get_finance_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.list_taxes = AsyncMock(return_value=[tax_1])
        mock_svc.create_tax = AsyncMock(return_value=tax_1)
        mock_svc.delete_tax = AsyncMock(return_value=None)

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)

        # List taxes
        res_list = client.get("/api/v1/admin/finance/taxes")
        assert res_list.status_code == 200
        assert len(res_list.json()["data"]) == 1
        assert res_list.json()["data"][0]["name"] == "Value Added Tax"

        # Create tax
        res_create = client.post(
            "/api/v1/admin/finance/taxes",
            json={
                "name": "Value Added Tax",
                "country": "Ethiopia",
                "value": 15.0,
                "type": "percentage",
                "isFix": False,
                "active": True,
            },
        )
        assert res_create.status_code == 201
        assert res_create.json()["name"] == "Value Added Tax"

        # Delete tax
        res_del = client.delete("/api/v1/admin/finance/taxes/1")
        assert res_del.status_code == 200
        assert res_del.json() == {"ok": True}


def test_get_chapa_balance_endpoint(api_client, super_admin_context):
    db = ApiTestDbSession()
    client = api_client(admin_context=super_admin_context, db_session=db)
    res = client.get("/api/v1/admin/finance/chapa-balance")

    assert res.status_code == 200
    data = res.json()
    assert data["currency"] == "ETB"
    assert "availableBalance" in data
    assert "ledgerBalance" in data
