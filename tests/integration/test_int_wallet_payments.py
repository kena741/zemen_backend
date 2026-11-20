"""Integration tests for Wallet and Payments endpoints.

Covers:
  - Wallet:
    - GET    /api/v1/wallet/balance
    - GET    /api/v1/wallet/transactions
    - GET    /api/v1/wallet/withdrawals
    - POST   /api/v1/wallet/withdrawals
    - GET    /api/v1/wallet/payment-methods
    - POST   /api/v1/wallet/payment-methods
    - DELETE /api/v1/wallet/payment-methods/{id}
  - Payments:
    - GET    /api/v1/payments/settings
    - GET    /api/v1/payments/taxes
    - GET    /api/v1/payments/status
    - GET    /api/v1/payments/chapa/banks
    - POST   /api/v1/payments/chapa/verify
"""

from __future__ import annotations

import uuid
import pytest
from httpx import AsyncClient


# ===========================================================================
# Wallet Endpoints
# ===========================================================================


@pytest.mark.asyncio
async def test_wallet_balance_unauthenticated_401(client: AsyncClient):
    """GET /api/v1/wallet/balance without auth returns 401."""
    resp = await client.get("/api/v1/wallet/balance")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_wallet_balance_customer_200(customer_client):
    """GET /api/v1/wallet/balance returns user wallet balance and ETB currency."""
    client, cust = customer_client
    resp = await client.get("/api/v1/wallet/balance")
    assert resp.status_code == 200
    data = resp.json()
    assert "balance" in data
    assert data["currency"] == "ETB"


@pytest.mark.asyncio
async def test_wallet_transactions_empty_200(customer_client):
    """GET /api/v1/wallet/transactions returns paginated ledger transactions."""
    client, cust = customer_client
    resp = await client.get("/api/v1/wallet/transactions")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_wallet_withdrawals_unauthenticated_401(client: AsyncClient):
    """GET /api/v1/wallet/withdrawals without auth returns 401."""
    resp = await client.get("/api/v1/wallet/withdrawals")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_wallet_withdrawals_provider_200(provider_client):
    """GET /api/v1/wallet/withdrawals returns provider withdrawal requests."""
    client, prov = provider_client
    resp = await client.get("/api/v1/wallet/withdrawals")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_wallet_withdrawals_not_blocked_by_legacy_503(provider_client):
    """POST /api/v1/wallet/withdrawals processes request without legacy 503 gating."""
    client, prov = provider_client
    payload = {
        "amount": 500.0,
        "note": "Weekly payout request",
    }
    resp = await client.post("/api/v1/wallet/withdrawals", json=payload)
    assert resp.status_code != 503


@pytest.mark.asyncio
async def test_provider_payment_methods_lifecycle(provider_client):
    """Provider registers a bank account, lists payout methods, and deletes it."""
    client, prov = provider_client

    # 1. Create payout method
    create_payload = {
        "bankName": "Commercial Bank of Ethiopia",
        "accountNumber": "1000123456789",
        "holderName": "Provider Test Account",
    }
    resp = await client.post("/api/v1/wallet/payment-methods", json=create_payload)
    assert resp.status_code == 201
    method_data = resp.json()
    method_id = method_data["id"]
    assert method_data["bankName"] == "Commercial Bank of Ethiopia"
    assert method_data["accountNumber"] == "1000123456789"

    # 2. List methods
    resp = await client.get("/api/v1/wallet/payment-methods")
    assert resp.status_code == 200
    items = resp.json()
    assert any(m["id"] == method_id for m in items)

    # 3. Delete payout method
    resp = await client.delete(f"/api/v1/wallet/payment-methods/{method_id}")
    assert resp.status_code == 204


# ===========================================================================
# Payments Endpoints
# ===========================================================================


@pytest.mark.asyncio
async def test_payments_settings_public_200(client: AsyncClient):
    """GET /api/v1/payments/settings returns public payment config."""
    resp = await client.get("/api/v1/payments/settings")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_payments_taxes_public_200(client: AsyncClient):
    """GET /api/v1/payments/taxes returns platform country taxes list."""
    resp = await client.get("/api/v1/payments/taxes")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_payments_status_public_200(client: AsyncClient):
    """GET /api/v1/payments/status returns migration phase status."""
    resp = await client.get("/api/v1/payments/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "enabled" in data
    assert "phase" in data


@pytest.mark.asyncio
async def test_payments_chapa_banks_public_200(client: AsyncClient):
    """GET /api/v1/payments/chapa/banks returns list of supported Ethiopian banks."""
    resp = await client.get("/api/v1/payments/chapa/banks")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_payments_chapa_verify_not_blocked(client: AsyncClient):
    """POST /api/v1/payments/chapa/verify executes transaction verification without legacy 503 gating."""
    resp = await client.post("/api/v1/payments/chapa/verify", json={"txRef": "test-tx-12345"})
    assert resp.status_code != 503
