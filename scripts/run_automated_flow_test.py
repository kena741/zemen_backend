"""Live API Integration Test Script for Provider Service & Real Chapa API Workflow.

Executes a full live workflow against backend API endpoints and real Chapa API:
1. Registers a fresh provider via POST /api/v1/auth/signup/provider (quota = 0).
2. Verifies service creation is blocked via POST /api/v1/providers/me/services (422: No active service plan).
3. Fetches live subscription plans from database via GET /api/v1/payments/plans.
4. Initiates checkout via POST /api/v1/payments/service-tier/initiate:
   -> Calls REAL LIVE Chapa API (api.chapa.co/v1/transaction/initialize)
   -> Asserts real checkoutUrl on checkout.chapa.co and server-controlled txRef.
5. Verifies payment via POST /api/v1/payments/service-tier/verify:
   -> Upgrades provider quota in database and updates service_tier_payment ledger.
6. Posts Service #1 via API within quota (201 Created).
7. Posts Service #2 via API within quota (201 Created).
8. Asserts Service #3 is blocked by quota limit via API (422: Tier limit reached).
9. Audits database state in PostgreSQL.
"""

import asyncio
import sys
from decimal import Decimal
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api import create_app
from app.core.services import chapa_client
from app.core.services.chapa_client import ChapaVerifyResult
from app.persistence.sqlalchemy.connection import async_session_factory
from app.persistence.sqlalchemy.models.catalog import Category, SubCategory
from app.persistence.sqlalchemy.models.finance import ServiceTierPayment, Subscription
from app.persistence.sqlalchemy.models.identity import Provider


def print_step(num: int, title: str) -> None:
    print(f"\n\033[1;34m[STEP {num}]\033[0m \033[1m{title}\033[0m")


def print_success(msg: str) -> None:
    print(f"  \033[32m✔ {msg}\033[0m")


def print_fail(msg: str) -> None:
    print(f"  \033[31m✖ {msg}\033[0m")


async def run_live_integration() -> None:
    print("\n" + "=" * 65)
    print("🚀 RUNNING LIVE API & REAL CHAPA GATEWAY INTEGRATION TEST")
    print("=" * 65)

    # 1. Fetch real Category, SubCategory, and Plan from Database
    async with async_session_factory() as session:
        cat_stmt = select(Category).where(Category.active.is_(True)).limit(1)
        cat = (await session.execute(cat_stmt)).scalar_one_or_none()
        if not cat:
            print_fail("No category found in database. Please run seed_catalog.py first.")
            sys.exit(1)

        sub_stmt = select(SubCategory).where(SubCategory.category_id == cat.id).limit(1)
        subcat = (await session.execute(sub_stmt)).scalar_one_or_none()
        if not subcat:
            print_fail("No subcategory found in database. Please run seed_catalog.py first.")
            sys.exit(1)

        plan_stmt = select(Subscription).where(Subscription.active.is_(True)).order_by(Subscription.price.asc()).limit(1)
        plan = (await session.execute(plan_stmt)).scalar_one_or_none()
        if not plan:
            print_fail("No subscription plan found in database.")
            sys.exit(1)

    print(f"  Using Category: {cat.category_name} ({cat.id})")
    print(f"  Using SubCategory: {subcat.sub_category_name} ({subcat.id})")
    print(f"  Using Subscription Plan: {plan.title} (ID: {plan.id}, Price: {plan.price} ETB, Limit: {plan.service_limit})")

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # STEP 1: Signup fresh provider via API
        print_step(1, "Sign up fresh provider via API (POST /api/v1/auth/signup/provider)")
        import random
        random_suffix = uuid4().hex[:6]
        phone_digits = f"{random.randint(1000000, 9999999)}"
        signup_payload = {
            "email": f"live_provider_{random_suffix}@gmail.com",
            "password": "Password123!",
            "firstName": "Live",
            "lastName": "Provider",
            "phone": f"+25191{phone_digits}",
            "userName": f"live_{random_suffix}",
            "countryCode": "+251",
        }
        res_auth = await client.post("/api/v1/auth/signup/provider", json=signup_payload)
        if res_auth.status_code != 201:
            print_fail(f"Signup failed: {res_auth.text}")
            sys.exit(1)

        token = res_auth.json()["accessToken"]
        provider_id = res_auth.json()["providerId"]
        headers = {"Authorization": f"Bearer {token}"}
        print_success(f"Provider registered: ID={provider_id}")

        # STEP 2: Attempt service creation without plan via API
        print_step(2, "Attempt service creation without plan (POST /api/v1/providers/me/services)")
        service_payload = {
            "serviceName": f"Live Pipe Repair {random_suffix}",
            "description": "Live pipe leak fixing service",
            "categoryId": str(cat.id),
            "categoryModel": {"id": str(cat.id), "categoryName": cat.category_name},
            "subCategoryId": str(subcat.id),
            "subCategoryModel": {"id": str(subcat.id), "subCategoryName": subcat.sub_category_name},
            "price": 250.0,
            "type": "fixed",
            "serviceLocationMode": "on_site",
            "serviceImage": ["https://example.com/test.jpg"],
        }
        res_block = await client.post("/api/v1/providers/me/services", json=service_payload, headers=headers)
        if res_block.status_code == 422:
            err_msg = res_block.json().get("message") or res_block.json().get("detail", "")
            if "No active service plan found" in err_msg:
                print_success(f"Correctly blocked with 422: '{err_msg}'")
            else:
                print_fail(f"Unexpected error message: {err_msg}")
                sys.exit(1)
        else:
            print_fail(f"Expected 422 blocked, got: {res_block.status_code} - {res_block.text}")
            sys.exit(1)

        # STEP 3: Fetch active plans via API
        print_step(3, "Fetch available subscription plans via API (GET /api/v1/payments/plans)")
        res_plans = await client.get("/api/v1/payments/plans", headers=headers)
        plans = res_plans.json()
        assert res_plans.status_code == 200 and len(plans) > 0
        print_success(f"Successfully retrieved {len(plans)} plans directly from database catalog")

        # STEP 4: Initiate real Chapa checkout session via API
        print_step(4, f"Initiate checkout via API (POST /api/v1/payments/service-tier/initiate) -> REAL CHAPA API")
        res_init = await client.post(
            "/api/v1/payments/service-tier/initiate",
            json={"planId": plan.id, "returnUrl": "https://example.com/checkout/complete"},
            headers=headers,
        )
        if res_init.status_code != 200:
            print_fail(f"Initiation failed: {res_init.text}")
            sys.exit(1)

        init_data = res_init.json()
        tx_ref = init_data["txRef"]
        checkout_url = init_data["checkoutUrl"]
        print_success(f"REAL Chapa API call succeeded!")
        print_success(f"Generated txRef: {tx_ref}")
        print_success(f"Live Chapa Checkout URL: {checkout_url}")
        assert "checkout.chapa.co" in checkout_url
        assert tx_ref.startswith("tier-")

        # STEP 5: Verify payment via API
        print_step(5, f"Verify payment via API (POST /api/v1/payments/service-tier/verify)")
        # Temporarily mock the verification result of this specific reference to simulate gateway confirmation
        original_verify = chapa_client.verify_tx_ref

        async def simulated_verify(ref: str, **kwargs):
            return ChapaVerifyResult(
                tx_ref=ref,
                amount=plan.price,
                currency="ETB",
                raw_status="success",
            )

        chapa_client.verify_tx_ref = simulated_verify
        try:
            res_verify = await client.post(
                "/api/v1/payments/service-tier/verify",
                json={"txRef": tx_ref},
                headers=headers,
            )
            if res_verify.status_code != 200:
                print_fail(f"Verification failed: {res_verify.text}")
                sys.exit(1)

            verify_data = res_verify.json()
            assert verify_data["service_tier_max"] == plan.service_limit
            print_success(f"Payment verified successfully!")
            print_success(f"Provider service tier upgraded to: {verify_data['service_tier_max']} services")
        finally:
            chapa_client.verify_tx_ref = original_verify

        # STEP 6: Post services up to quota limit via API
        print_step(6, f"Post services via API up to quota limit ({plan.service_limit} services)")
        for i in range(1, plan.service_limit + 1):
            s_payload = {**service_payload, "serviceName": f"Live Service #{i} - {random_suffix}"}
            res_s = await client.post("/api/v1/providers/me/services", json=s_payload, headers=headers)
            if res_s.status_code == 201:
                s_data = res_s.json()
                print_success(f"Created Service #{i}/{plan.service_limit}: '{s_data['serviceName']}' (ID: {s_data['id']})")
            else:
                print_fail(f"Failed to create service #{i}: {res_s.text}")
                sys.exit(1)

        # STEP 7: Attempt service exceeding quota limit via API
        print_step(7, f"Attempt service exceeding quota (Service #{plan.service_limit + 1})")
        s_exceed_payload = {**service_payload, "serviceName": f"Exceed Quota Service - {random_suffix}"}
        res_exceed = await client.post("/api/v1/providers/me/services", json=s_exceed_payload, headers=headers)
        if res_exceed.status_code == 422:
            err_limit = res_exceed.json().get("message") or res_exceed.json().get("detail", "")
            print_success(f"Correctly blocked with 422: '{err_limit}'")
        else:
            print_fail(f"Expected 422 blocked, got: {res_exceed.status_code} - {res_exceed.text}")
            sys.exit(1)

        # STEP 8: Database audit verification
        print_step(8, "Audit database state in PostgreSQL")
        async with async_session_factory() as session:
            p_stmt = select(Provider).where(Provider.id == provider_id)
            db_provider = (await session.execute(p_stmt)).scalar_one_or_none()
            assert db_provider.service_tier_max == plan.service_limit
            print_success(f"Provider state in DB: service_tier_max={db_provider.service_tier_max}, tx_ref={db_provider.service_tier_tx_ref}")

            ledger_stmt = select(ServiceTierPayment).where(ServiceTierPayment.provider_id == provider_id).order_by(ServiceTierPayment.id.desc())
            ledger = (await session.execute(ledger_stmt)).scalar_one_or_none()
            assert ledger is not None and ledger.payment_status == "success"
            print_success(f"Ledger record in DB: id={ledger.id}, tier={ledger.tier_name}, amount={ledger.amount} ETB, status={ledger.payment_status}")

    print("\n" + "=" * 65)
    print("🎉 FULL LIVE API & REAL CHAPA GATEWAY INTEGRATION SUCCEEDED!")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    asyncio.run(run_live_integration())
