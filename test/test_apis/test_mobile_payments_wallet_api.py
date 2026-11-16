"""Integration tests for Mobile Payments and Wallet APIs."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1.routers.payments import get_chapa_payment_service
from app.api.v1.routers.wallet import get_wallet_service
from app.core.security.deps import AuthContext
from app.domain.finance import (
    CountryTaxDomain,
    EnrichedWalletTransactionDomain,
    ProviderPaymentMethodDomain,
    WithdrawalDomain,
)


@pytest.fixture
def mock_payment_service():
    return AsyncMock()


@pytest.fixture
def mock_wallet_service():
    return AsyncMock()


def test_payments_settings_and_banks(api_client, mock_payment_service):
    mock_payment_service.get_payment_settings.return_value = {
        "chapaPublicKey": "CHAPUBK_TEST-mobile-key",
        "isTest": True,
        "currency": "ETB",
        "paymentMethods": ["chapa", "wallet"],
    }
    mock_payment_service.list_taxes.return_value = [
        CountryTaxDomain(id=1, name="VAT", country="Ethiopia", value=15.0)
    ]
    mock_payment_service.list_supported_banks.return_value = [
        {"id": "cbe", "name": "Commercial Bank of Ethiopia", "code": "CBE"}
    ]

    client = api_client()
    client.app.dependency_overrides[get_chapa_payment_service] = lambda: mock_payment_service

    # Settings
    res_set = client.get("/api/v1/payments/settings")
    assert res_set.status_code == 200
    assert res_set.json()["chapaPublicKey"] == "CHAPUBK_TEST-mobile-key"

    # Taxes
    res_tax = client.get("/api/v1/payments/taxes")
    assert res_tax.status_code == 200
    assert len(res_tax.json()) == 1
    assert res_tax.json()[0]["value"] == 15.0

    # Banks
    res_bnk = client.get("/api/v1/payments/chapa/banks")
    assert res_bnk.status_code == 200
    assert len(res_bnk.json()) == 1
    assert res_bnk.json()[0]["code"] == "CBE"


def test_chapa_verifications(api_client, mock_payment_service):
    prov_id = uuid4()
    srv_id = uuid4()

    mock_payment_service.verify_provider_activation.return_value = {
        "status": "success",
        "activation_paid": True,
    }
    mock_payment_service.verify_service_tier_payment.return_value = {
        "status": "success",
        "service_tier_max": 10,
    }
    mock_payment_service.verify_featured_request_payment.return_value = {
        "status": "success",
        "feature": True,
    }

    client = api_client()
    client.app.dependency_overrides[get_chapa_payment_service] = lambda: mock_payment_service

    # Activation verify
    res_act = client.post(
        "/api/v1/payments/provider-activation/verify",
        json={"txRef": "tx_act_123", "providerId": str(prov_id), "amount": 500.0},
    )
    assert res_act.status_code == 200
    assert res_act.json()["activation_paid"] is True

    # Tier verify
    res_tier = client.post(
        "/api/v1/payments/service-tier/verify",
        json={"txRef": "tx_tier_123", "providerId": str(prov_id), "tierMax": 10, "amount": 1000.0},
    )
    assert res_tier.status_code == 200
    assert res_tier.json()["service_tier_max"] == 10

    # Featured verify
    res_feat = client.post(
        "/api/v1/payments/featured-request/verify",
        json={
            "txRef": "tx_feat_123",
            "providerId": str(prov_id),
            "serviceId": str(srv_id),
            "amount": 250.0,
        },
    )
    assert res_feat.status_code == 200
    assert res_feat.json()["feature"] is True


def test_wallet_balance_and_transactions(api_client, mock_wallet_service):
    user_id = uuid4()
    cust_id = uuid4()

    mock_wallet_service.get_balance.return_value = 1250.50
    mock_wallet_service.list_transactions.return_value = [
        EnrichedWalletTransactionDomain(
            id=uuid4(),
            amount="500.00",
            is_credit=True,
            note="Refund for booking",
            type="customer",
        )
    ]

    ctx = AuthContext(
        user_id=user_id,
        email="customer@example.com",
        roles=["customer"],
        customer_id=cust_id,
    )
    client = api_client(auth_context=ctx)
    client.app.dependency_overrides[get_wallet_service] = lambda: mock_wallet_service

    # Balance
    res_bal = client.get("/api/v1/wallet/balance")
    assert res_bal.status_code == 200
    assert res_bal.json()["balance"] == 1250.50

    # Transactions
    res_tx = client.get("/api/v1/wallet/transactions")
    assert res_tx.status_code == 200
    assert len(res_tx.json()["items"]) == 1
    assert res_tx.json()["items"][0]["amount"] == "500.00"


def test_provider_withdrawals_and_payment_methods(api_client, mock_wallet_service):
    user_id = uuid4()
    prov_id = uuid4()
    w_id = uuid4()
    pm_id = uuid4()

    mock_wallet_service.list_withdrawals.return_value = [
        WithdrawalDomain(
            id=w_id,
            provider_id=prov_id,
            amount=600.0,
            payment_status="pending",
        )
    ]
    mock_wallet_service.request_withdrawal.return_value = WithdrawalDomain(
        id=w_id,
        provider_id=prov_id,
        amount=600.0,
        payment_status="pending",
    )
    mock_wallet_service.list_payment_methods.return_value = [
        ProviderPaymentMethodDomain(
            id=pm_id,
            provider_id=prov_id,
            bank_name="Dashen Bank",
            account_number="543210987654",
        )
    ]
    mock_wallet_service.create_payment_method.return_value = ProviderPaymentMethodDomain(
        id=pm_id,
        provider_id=prov_id,
        bank_name="Dashen Bank",
        account_number="543210987654",
    )

    ctx = AuthContext(
        user_id=user_id,
        email="provider@example.com",
        roles=["provider"],
        provider_id=prov_id,
    )
    client = api_client(auth_context=ctx)
    client.app.dependency_overrides[get_wallet_service] = lambda: mock_wallet_service

    # List withdrawals
    res_w = client.get("/api/v1/wallet/withdrawals")
    assert res_w.status_code == 200
    assert len(res_w.json()["items"]) == 1

    # Request withdrawal
    res_rw = client.post(
        "/api/v1/wallet/withdrawals",
        json={"amount": 600.0, "paymentMethodId": str(pm_id)},
    )
    assert res_rw.status_code == 201
    assert float(res_rw.json()["amount"]) == 600.0

    # List payment methods
    res_pm = client.get("/api/v1/wallet/payment-methods")
    assert res_pm.status_code == 200
    assert len(res_pm.json()) == 1

    # Add payment method
    res_cpm = client.post(
        "/api/v1/wallet/payment-methods",
        json={"bankName": "Dashen Bank", "accountNumber": "543210987654"},
    )
    assert res_cpm.status_code == 201
    assert res_cpm.json()["bankName"] == "Dashen Bank"

    # Delete payment method
    res_dpm = client.delete(f"/api/v1/wallet/payment-methods/{pm_id}")
    assert res_dpm.status_code == 204
