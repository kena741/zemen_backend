"""
Integration tests: /api/v1/config endpoints.

Covers:
  - GET /api/v1/config/banners
  - GET /api/v1/config/taxes
  - GET /api/v1/config/coupons
  - GET /api/v1/config/currencies
  - GET /api/v1/config/currency
  - GET /api/v1/config/languages
  - GET /api/v1/config/settings/{setting_id}
  - GET /api/v1/config/mobile/{app_key}
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models.config import (
    AppSetting,
    Banner,
    CountryTax,
    Coupon,
    Currency,
    Language,
    MobileAppConfig,
)


@pytest.mark.asyncio
async def test_list_banners_empty(client: AsyncClient):
    resp = await client.get("/api/v1/config/banners")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_banners_active_filter(client: AsyncClient, db_session: AsyncSession):
    now = datetime.now(timezone.utc)
    b1 = Banner(banner_name="Active Banner", image="https://example.com/b1.jpg", active=True, created_at=now)
    b2 = Banner(banner_name="Inactive Banner", image="https://example.com/b2.jpg", active=False, created_at=now)
    db_session.add_all([b1, b2])
    await db_session.flush()

    # Default activeOnly=True
    resp = await client.get("/api/v1/config/banners")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["bannerName"] == "Active Banner"

    # activeOnly=False
    resp_all = await client.get("/api/v1/config/banners", params={"activeOnly": "false"})
    assert resp_all.status_code == 200
    assert len(resp_all.json()) == 2


@pytest.mark.asyncio
async def test_list_taxes_filter(client: AsyncClient, db_session: AsyncSession):
    now = datetime.now(timezone.utc)
    t1 = CountryTax(name="VAT", country="ET", value=Decimal("15.0"), is_fix=False, active=True, created_at=now)
    t2 = CountryTax(name="Old Tax", country="ET", value=Decimal("2.0"), is_fix=True, active=False, created_at=now)
    db_session.add_all([t1, t2])
    await db_session.flush()

    resp = await client.get("/api/v1/config/taxes")
    assert resp.status_code == 200
    taxes = resp.json()
    assert len(taxes) == 1
    assert taxes[0]["name"] == "VAT"

    resp_all = await client.get("/api/v1/config/taxes", params={"activeOnly": "false"})
    assert resp_all.status_code == 200
    assert len(resp_all.json()) == 2


@pytest.mark.asyncio
async def test_list_coupons_public_only(client: AsyncClient, db_session: AsyncSession):
    now = datetime.now(timezone.utc)
    c1 = Coupon(title="SUMMER10", code="SUMMER10", amount=Decimal("10.0"), is_private=False, active=True, created_at=now)
    c2 = Coupon(title="PRIVATEVIP", code="PRIVATEVIP", amount=Decimal("50.0"), is_private=True, active=True, created_at=now)
    db_session.add_all([c1, c2])
    await db_session.flush()

    resp = await client.get("/api/v1/config/coupons")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["code"] == "SUMMER10"


@pytest.mark.asyncio
async def test_list_and_get_active_currency(client: AsyncClient, db_session: AsyncSession):
    now = datetime.now(timezone.utc)
    c_etb = Currency(name="Ethiopian Birr", symbol="Br", active=True, created_at=now)
    c_usd = Currency(name="US Dollar", symbol="$", active=False, created_at=now)
    db_session.add_all([c_etb, c_usd])
    await db_session.flush()

    # Active currencies
    resp = await client.get("/api/v1/config/currencies")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    names = [c["name"] for c in data]
    assert "Ethiopian Birr" in names

    # Single active currency
    curr_resp = await client.get("/api/v1/config/currency")
    assert curr_resp.status_code == 200
    curr = curr_resp.json()
    assert curr is not None
    assert curr["name"] == "Ethiopian Birr"


@pytest.mark.asyncio
async def test_list_languages(client: AsyncClient, db_session: AsyncSession):
    l1 = Language(id=uuid4(), name="Amharic", code="am", active=True)
    l2 = Language(id=uuid4(), name="English", code="en", active=True)
    db_session.add_all([l1, l2])
    await db_session.flush()

    resp = await client.get("/api/v1/config/languages")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2
    codes = [lang["code"] for lang in data]
    assert "am" in codes
    assert "en" in codes


@pytest.mark.asyncio
async def test_get_app_setting_with_secret_redaction(client: AsyncClient, db_session: AsyncSession):
    now = datetime.now(timezone.utc)
    setting = AppSetting(
        id="payment",
        data={
            "chapa_public_key": "CHAPUBK_TEST-12345",
            "chapa_secret_key": "CHASECK_TEST-SECRET999",
            "currency": "ETB",
        },
        updated_at=now,
    )
    db_session.add(setting)
    await db_session.flush()

    resp = await client.get("/api/v1/config/settings/payment")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "payment"
    # Secret must be redacted
    assert "chapa_secret_key" not in data["data"]
    assert data["data"]["chapa_public_key"] == "CHAPUBK_TEST-12345"
    assert data["data"]["currency"] == "ETB"


@pytest.mark.asyncio
async def test_get_app_setting_404(client: AsyncClient):
    resp = await client.get("/api/v1/config/settings/nonexistent_setting")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_mobile_config_when_present(client: AsyncClient, db_session: AsyncSession):
    now = datetime.now(timezone.utc)
    cfg = MobileAppConfig(
        app_key="customer_app",
        maintenance_mode=False,
        maintenance_message="Under scheduled maintenance",
        maintenance_affected_versions=[],
        update_needed=False,
        update_affected_versions=[],
        created_at=now,
        updated_at=now,
    )
    db_session.add(cfg)
    await db_session.flush()

    resp = await client.get("/api/v1/config/mobile/customer_app")
    assert resp.status_code == 200
    data = resp.json()
    assert data["app_key"] == "customer_app"
    assert data["maintenance_mode"] is False

