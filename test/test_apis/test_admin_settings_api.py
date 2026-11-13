"""Integration tests for Admin Settings, Languages, Mobile App Config, Coupons, and Nav Action Counts API endpoints."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

import app.api.v1.routers.admin.settings as admin_settings_module
from app.core.security.admin_deps import AdminContext
from app.domain.settings import (
    CouponDomain,
    LanguageDomain,
    MobileAppConfigDomain,
    NavActionCountsDomain,
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


def test_get_settings_api(api_client, super_admin_context):
    mock_settings = {
        "app_settings": {"platform_name": "Zemen Admin"},
        "general_settings": {},
        "policy_settings": {},
        "payment_settings": {"chapa_active": True},
        "contact_us": {"email": "support@zemen.com"},
        "admin_commission": {"percentage": 10},
        "status_options": [],
        "constants": {},
        "language_settings": [
            LanguageDomain(id=uuid4(), code="en", name="English", active=True)
        ],
        "languages": [
            LanguageDomain(id=uuid4(), code="en", name="English", active=True)
        ],
    }

    with patch("app.api.v1.routers.admin.settings._get_settings_service") as mock_svc_getter:
        mock_svc = mock_svc_getter.return_value
        mock_svc.get_settings = AsyncMock(return_value=mock_settings)

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.get("/api/v1/admin/settings")

        assert res.status_code == 200
        data = res.json()
        assert data["appSettings"]["platform_name"] == "Zemen Admin"
        assert data["paymentSettings"]["chapa_active"] is True
        assert len(data["languageSettings"]) == 1


def test_update_settings_api(api_client, super_admin_context):
    with patch("app.api.v1.routers.admin.settings._get_settings_service") as mock_svc_getter:
        mock_svc = mock_svc_getter.return_value
        mock_svc.update_settings = AsyncMock(return_value={"app_rows": [], "language_rows": []})

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        payload = {
            "paymentSettings": {"chapa_active": True},
            "contactUs": {"email": "hello@zemen.com"},
        }
        res = client.post("/api/v1/admin/settings", json=payload)

        assert res.status_code == 200
        assert "data" in res.json()


def test_bulk_mutate_languages_api(api_client, super_admin_context):
    with patch("app.api.v1.routers.admin.settings._get_settings_service") as mock_svc_getter:
        mock_svc = mock_svc_getter.return_value
        mock_svc.bulk_mutate_languages = AsyncMock(return_value=None)

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        payload = {
            "upserts": [{"code": "am", "name": "Amharic", "active": True}],
        }
        res = client.post("/api/v1/settings/languages", json=payload)

        assert res.status_code == 200
        assert res.json() == {"ok": True}


def test_mobile_app_config_api(api_client, super_admin_context):
    cfg = MobileAppConfigDomain(
        app_key="customer_app",
        maintenance_mode=True,
        maintenance_message="Scheduled maintenance",
        maintenance_affected_versions=[],
        update_needed=False,
        update_message="",
        update_affected_versions=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    with patch("app.api.v1.routers.admin.settings._get_settings_service") as mock_svc_getter:
        mock_svc = mock_svc_getter.return_value
        mock_svc.list_mobile_app_configs = AsyncMock(return_value=[cfg])
        mock_svc.update_mobile_app_config = AsyncMock(return_value=cfg)

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)

        # List configs
        list_res = client.get("/api/v1/admin/mobile-app-config")
        assert list_res.status_code == 200
        configs = list_res.json()["data"]
        assert len(configs) == 1
        assert configs[0]["appKey"] == "customer_app"
        assert configs[0]["maintenanceMode"] is True

        # Patch config
        patch_res = client.patch(
            "/api/v1/admin/mobile-app-config",
            json={"appKey": "customer_app", "maintenanceMode": True},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["data"]["appKey"] == "customer_app"


def test_nav_action_counts_api(api_client, super_admin_context):
    counts = NavActionCountsDomain(
        payout_requests=3,
        verify_documents=5,
        approve_services=2,
        bookings=8,
        job_requests=4,
    )

    with patch("app.api.v1.routers.admin.settings._get_settings_service") as mock_svc_getter:
        mock_svc = mock_svc_getter.return_value
        mock_svc.get_nav_action_counts = AsyncMock(return_value=counts)

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.get("/api/v1/admin/nav-action-counts")

        assert res.status_code == 200
        res_counts = res.json()["counts"]
        assert res_counts["/admin/finance/payout-request"] == 3
        assert res_counts["/admin/verify-documents"] == 5
        assert res_counts["/admin/services/approve"] == 2
        assert res_counts["/admin/bookings"] == 8
        assert res_counts["/admin/customers/job-requests"] == 4


def test_coupons_api(api_client, super_admin_context):
    coupon = CouponDomain(
        id=1,
        title="Discount 20",
        code="SAVE20",
        amount=Decimal("20.00"),
        min_amount=Decimal("100.00"),
        active=True,
        created_at=datetime.now(timezone.utc),
    )

    with patch("app.api.v1.routers.admin.settings._get_settings_service") as mock_svc_getter:
        mock_svc = mock_svc_getter.return_value
        mock_svc.list_coupons = AsyncMock(return_value=[coupon])
        mock_svc.create_coupon = AsyncMock(return_value=coupon)
        mock_svc.update_coupon = AsyncMock(return_value=coupon)
        mock_svc.delete_coupon = AsyncMock(return_value=None)

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)

        # List coupons
        list_res = client.get("/api/v1/admin/coupons")
        assert list_res.status_code == 200
        assert len(list_res.json()["data"]) == 1
        assert list_res.json()["data"][0]["code"] == "SAVE20"

        # Create coupon
        create_res = client.post(
            "/api/v1/admin/coupons",
            json={"title": "Discount 20", "code": "SAVE20", "amount": 20.0},
        )
        assert create_res.status_code == 201

        # Patch coupon
        patch_res = client.patch(
            "/api/v1/admin/coupons/1",
            json={"active": False},
        )
        assert patch_res.status_code == 200

        # Delete coupon
        del_res = client.delete("/api/v1/admin/coupons/1")
        assert del_res.status_code == 200
        assert del_res.json() == {"ok": True}
