"""Unit tests for SettingsAdminService covering Platform Settings, Languages, Mobile Config, Coupons, and Nav Action Counts."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.security.admin_deps import AdminContext
from app.core.services.admin.settings_service import SettingsAdminService
from app.domain.settings import (
    AppSettingDomain,
    CouponDomain,
    LanguageDomain,
    MobileAppConfigDomain,
    NavActionCountsDomain,
)


@pytest.fixture
def mock_admin_ctx() -> AdminContext:
    return AdminContext(
        admin_id=uuid4(),
        user_id=uuid4(),
        email="settings_admin@example.com",
        full_name="Settings Admin",
        role="super_admin",
        permissions=["*"],
    )


@pytest.mark.asyncio
async def test_get_settings():
    app_settings_repo = AsyncMock()
    language_repo = AsyncMock()
    mobile_config_repo = AsyncMock()
    coupon_repo = AsyncMock()
    nav_action_counts_repo = AsyncMock()
    audit_service = AsyncMock()

    app_settings_repo.list_all_settings.return_value = [
        AppSettingDomain(id="payment", data={"chapa_enabled": True}),
        AppSettingDomain(id="contact_us", data={"phone": "+251911223344"}),
    ]
    language_repo.list_languages.return_value = [
        LanguageDomain(id=uuid4(), code="en", name="English", active=True),
        LanguageDomain(id=uuid4(), code="am", name="Amharic", active=True),
    ]

    service = SettingsAdminService(
        app_settings_repo=app_settings_repo,
        language_repo=language_repo,
        mobile_config_repo=mobile_config_repo,
        coupon_repo=coupon_repo,
        nav_action_counts_repo=nav_action_counts_repo,
        audit_service=audit_service,
    )

    settings = await service.get_settings()
    assert settings["payment_settings"]["chapa_enabled"] is True
    assert settings["contact_us"]["phone"] == "+251911223344"
    assert len(settings["languages"]) == 2


@pytest.mark.asyncio
async def test_update_settings(mock_admin_ctx):
    app_settings_repo = AsyncMock()
    language_repo = AsyncMock()
    mobile_config_repo = AsyncMock()
    coupon_repo = AsyncMock()
    nav_action_counts_repo = AsyncMock()
    audit_service = AsyncMock()

    app_settings_repo.upsert_setting.return_value = AppSettingDomain(
        id="payment", data={"chapa_enabled": True}
    )
    language_repo.upsert_language.return_value = LanguageDomain(
        id=uuid4(), code="om", name="Oromo", active=True
    )
    language_repo.delete_languages.return_value = 1

    service = SettingsAdminService(
        app_settings_repo=app_settings_repo,
        language_repo=language_repo,
        mobile_config_repo=mobile_config_repo,
        coupon_repo=coupon_repo,
        nav_action_counts_repo=nav_action_counts_repo,
        audit_service=audit_service,
    )

    payload = {
        "paymentSettings": {"chapa_enabled": True},
        "languageSettings": [{"code": "om", "name": "Oromo", "active": True}],
        "languageDeletedIds": [uuid4()],
    }

    res = await service.update_settings(payload, ctx=mock_admin_ctx)
    assert len(res["app_rows"]) == 1
    assert len(res["language_rows"]) == 1
    assert app_settings_repo.upsert_setting.called
    assert language_repo.upsert_language.called
    assert language_repo.delete_languages.called
    assert audit_service.log_action.called


@pytest.mark.asyncio
async def test_bulk_mutate_languages(mock_admin_ctx):
    language_repo = AsyncMock()
    audit_service = AsyncMock()
    del_id = uuid4()

    service = SettingsAdminService(
        app_settings_repo=AsyncMock(),
        language_repo=language_repo,
        mobile_config_repo=AsyncMock(),
        coupon_repo=AsyncMock(),
        nav_action_counts_repo=AsyncMock(),
        audit_service=audit_service,
    )

    await service.bulk_mutate_languages(
        upserts=[{"code": "ti", "name": "Tigrinya"}],
        inserts=[],
        delete_ids=[del_id],
        ctx=mock_admin_ctx,
    )

    assert language_repo.upsert_language.called
    assert language_repo.delete_languages.called
    assert audit_service.log_action.called


@pytest.mark.asyncio
async def test_mobile_app_config_crud(mock_admin_ctx):
    mobile_config_repo = AsyncMock()
    audit_service = AsyncMock()

    cfg = MobileAppConfigDomain(app_key="customer_app", maintenance_mode=True)
    mobile_config_repo.list_configs.return_value = [cfg]
    mobile_config_repo.update_config.return_value = cfg

    service = SettingsAdminService(
        app_settings_repo=AsyncMock(),
        language_repo=AsyncMock(),
        mobile_config_repo=mobile_config_repo,
        coupon_repo=AsyncMock(),
        nav_action_counts_repo=AsyncMock(),
        audit_service=audit_service,
    )

    configs = await service.list_mobile_app_configs()
    assert len(configs) == 1

    updated = await service.update_mobile_app_config(
        "customer_app", {"maintenance_mode": True}, ctx=mock_admin_ctx
    )
    assert updated.maintenance_mode is True

    # Not found case
    mobile_config_repo.update_config.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.update_mobile_app_config("unknown_app", {}, ctx=mock_admin_ctx)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_coupons_crud(mock_admin_ctx):
    coupon_repo = AsyncMock()
    audit_service = AsyncMock()

    coupon = CouponDomain(
        id=1,
        title="Spring Promo",
        code="SPRING50",
        amount=Decimal("50.00"),
        min_amount=Decimal("200.00"),
    )
    coupon_repo.list_coupons.return_value = [coupon]
    coupon_repo.get_coupon_by_id.return_value = coupon
    coupon_repo.get_by_code.return_value = None
    coupon_repo.create_coupon.return_value = coupon
    coupon_repo.update_coupon.return_value = coupon
    coupon_repo.delete_coupon.return_value = True

    service = SettingsAdminService(
        app_settings_repo=AsyncMock(),
        language_repo=AsyncMock(),
        mobile_config_repo=AsyncMock(),
        coupon_repo=coupon_repo,
        nav_action_counts_repo=AsyncMock(),
        audit_service=audit_service,
    )

    coupons = await service.list_coupons()
    assert len(coupons) == 1

    created = await service.create_coupon(
        {"title": "Spring Promo", "code": "SPRING50", "amount": Decimal("50.00")},
        ctx=mock_admin_ctx,
    )
    assert created.code == "SPRING50"

    # Conflict on duplicate code
    coupon_repo.get_by_code.return_value = coupon
    with pytest.raises(HTTPException) as exc_info:
        await service.create_coupon({"code": "SPRING50"}, ctx=mock_admin_ctx)
    assert exc_info.value.status_code == 409

    updated = await service.update_coupon(1, {"active": False}, ctx=mock_admin_ctx)
    assert updated.id == 1

    await service.delete_coupon(1, ctx=mock_admin_ctx)
    assert coupon_repo.delete_coupon.called


@pytest.mark.asyncio
async def test_nav_action_counts():
    nav_repo = AsyncMock()
    nav_repo.get_aggregated_counts.return_value = NavActionCountsDomain(
        payout_requests=2,
        verify_documents=4,
        approve_services=1,
        bookings=12,
        job_requests=3,
    )

    service = SettingsAdminService(
        app_settings_repo=AsyncMock(),
        language_repo=AsyncMock(),
        mobile_config_repo=AsyncMock(),
        coupon_repo=AsyncMock(),
        nav_action_counts_repo=nav_repo,
        audit_service=AsyncMock(),
    )

    counts = await service.get_nav_action_counts()
    assert counts.payout_requests == 2
    assert counts.total == 22
    assert counts.to_dict()["/admin/finance/payout-request"] == 2

