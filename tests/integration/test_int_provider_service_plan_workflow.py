"""End-to-end integration test for backend-driven provider plan purchasing and service quota enforcement.

Workflow under test:
1. Provider registers/signs in without a plan (service_tier_max = 0).
2. Provider attempts to create a service -> Blocked with 422 (No active service plan found).
3. Provider fetches available plans from database: GET /api/v1/payments/plans.
4. Provider initiates checkout via backend: POST /api/v1/payments/service-tier/initiate {"planId": plan_id}.
   -> Backend creates server-controlled tx_ref, links quota, logs pending ServiceTierPayment.
5. Provider verifies transaction with just txRef: POST /api/v1/payments/service-tier/verify {"txRef": tx_ref}.
   -> Backend verifies with Chapa, updates ledger to "success", upgrades provider service_tier_max.
6. Provider creates Service #1 within quota -> 201 Created.
7. Provider creates Service #2 within quota -> 201 Created.
8. Provider attempts to create Service #3 exceeding quota -> Blocked with 422 (Tier limit reached).
9. Ledger audit: verify ServiceTierPayment record exists with status 'success'.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.services import chapa_client
from app.core.services.chapa_client import ChapaInitializeResult, ChapaVerifyResult
from app.persistence.sqlalchemy.connection import async_session_factory
from app.persistence.sqlalchemy.models.finance import ServiceTierPayment, Subscription


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_provider_plan_and_service_quota_lifecycle(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_provider,
    seed_category,
    seed_subcategory,
    monkeypatch,
):
    # Ensure active subscription plan exists in test db session
    now = datetime.now(timezone.utc)
    plan_price = Decimal("500.00")
    plan_limit = 2
    plan = Subscription(
        title="Starter Plan",
        price=plan_price,
        service_limit=plan_limit,
        description="Up to 2 services",
        duration="1 Month",
        plan_type="tier",
        active=True,
        is_subscribed=False,
        created_at=now,
        updated_at=now,
    )
    db_session.add(plan)
    await db_session.flush()
    plan_id = plan.id

    # Real Chapa API integration for checkout initialization when secret key is present
    from app.config import settings

    if not (settings.CHAPA_SECRET_KEY or "").strip():
        async def mock_init_tx(**kwargs):
            ref = kwargs.get("tx_ref")
            return ChapaInitializeResult(
                tx_ref=ref,
                checkout_url=f"https://checkout.chapa.co/checkout/web/session-{ref}",
                status="success",
                message="Checkout session initialized successfully",
            )
        monkeypatch.setattr(chapa_client, "initialize_transaction", mock_init_tx)

    async def mock_verify_tx(ref, **kwargs):
        return ChapaVerifyResult(
            tx_ref=ref,
            amount=plan_price,
            currency="ETB",
            raw_status="success",
        )

    monkeypatch.setattr(chapa_client, "verify_tx_ref", mock_verify_tx)

    # 1. Provider signs in with NO PLAN (service_tier_max = 0)
    prov, user_id, _, token = await seed_provider(service_tier_max=0)
    provider_id = prov.id
    client.headers.update(_auth_headers(token))

    cat = await seed_category(name="Plumbing & Repairs")
    subcat = await seed_subcategory(category_id=cat.id, name="Pipe Fixing")

    service_payload = {
        "serviceName": "Pipe Leak Repair",
        "description": "Emergency pipe leak fixing",
        "categoryId": str(cat.id),
        "categoryModel": {"id": str(cat.id), "categoryName": cat.category_name},
        "subCategoryId": str(subcat.id),
        "subCategoryModel": {"id": str(subcat.id), "subCategoryName": subcat.sub_category_name},
        "type": "fixed",
        "serviceLocationMode": "provider_location",
        "price": 300.0,
        "serviceImage": ["https://example.com/pipe.jpg"],
    }

    # 2. Attempt service creation without plan -> MUST BE BLOCKED WITH 422
    res_no_plan = await client.post("/api/v1/providers/me/services", json=service_payload)
    assert res_no_plan.status_code == 422
    err_detail = res_no_plan.json().get("message") or res_no_plan.json().get("detail", "")
    assert "No active service plan found" in err_detail

    # 3. List available subscription plans: GET /api/v1/payments/plans
    res_plans = await client.get("/api/v1/payments/plans")
    assert res_plans.status_code == 200
    plans_list = res_plans.json()
    assert len(plans_list) > 0
    matched_plan = next((p for p in plans_list if p["id"] == plan_id), None)
    assert matched_plan is not None
    assert matched_plan["serviceLimit"] == plan_limit

    # 4. Initiate tier checkout via backend: POST /api/v1/payments/service-tier/initiate
    init_res = await client.post(
        "/api/v1/payments/service-tier/initiate",
        json={
            "planId": plan_id,
            "returnUrl": "https://example.com/checkout/return",
        },
    )
    assert init_res.status_code == 200
    init_data = init_res.json()
    assert init_data["status"] == "success"
    assert "checkout.chapa.co" in init_data["checkoutUrl"]
    assert init_data["txRef"].startswith("tier-")
    backend_tx_ref = init_data["txRef"]

    # 5. Verify payment with backend using ONLY txRef (no client tampering)
    verify_res = await client.post(
        "/api/v1/payments/service-tier/verify",
        json={
            "txRef": backend_tx_ref,
        },
    )
    assert verify_res.status_code == 200
    verify_data = verify_res.json()
    assert verify_data["status"] == "success"
    assert verify_data["service_tier_max"] == plan_limit
    assert verify_data["tx_ref"] == backend_tx_ref

    # 6. Create Service 1 within quota (1 / plan_limit) -> SUCCESS (201)
    service_payload_1 = {**service_payload, "serviceName": "Pipe Leak Repair"}
    res_s1 = await client.post("/api/v1/providers/me/services", json=service_payload_1)
    assert res_s1.status_code == 201
    s1_data = res_s1.json()
    assert s1_data["serviceName"] == "Pipe Leak Repair"

    # 7. Create Service 2 within quota (2 / plan_limit) -> SUCCESS (201)
    service_payload_2 = {**service_payload, "serviceName": "Drain Cleaning"}
    res_s2 = await client.post("/api/v1/providers/me/services", json=service_payload_2)
    assert res_s2.status_code == 201
    s2_data = res_s2.json()
    assert s2_data["serviceName"] == "Drain Cleaning"

    # 8. Attempt Service 3 exceeding quota -> MUST BE BLOCKED WITH 422
    service_payload_3 = {**service_payload, "serviceName": "Water Heater Installation"}
    res_s3 = await client.post("/api/v1/providers/me/services", json=service_payload_3)
    assert res_s3.status_code == 422
    err_limit = res_s3.json().get("message") or res_s3.json().get("detail", "")
    assert "Tier limit reached" in err_limit
    assert f"{plan_limit}/{plan_limit}" in err_limit

    # 9. Verify database audit ledger (ServiceTierPayment) has status="success"
    ledger_stmt = (
        select(ServiceTierPayment)
        .where(ServiceTierPayment.provider_id == provider_id)
        .order_by(ServiceTierPayment.created_at.desc())
    )
    ledger_res = await db_session.execute(ledger_stmt)
    tier_payment_record = ledger_res.scalars().first()
    assert tier_payment_record is not None
    assert tier_payment_record.payment_status == "success"
    assert tier_payment_record.tier_id == plan_limit
    assert tier_payment_record.amount == plan_price
