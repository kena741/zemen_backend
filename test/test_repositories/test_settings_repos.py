"""Unit and mapping tests for Settings, Languages, Mobile App Config, Coupons, and Nav Action Counts repositories."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.persistence.repositories.app_settings_repo import AppSettingsRepository
from app.persistence.repositories.coupon_repo import CouponRepository
from app.persistence.repositories.language_repo import LanguageRepository
from app.persistence.repositories.mobile_app_config_repo import MobileAppConfigRepository
from app.persistence.repositories.nav_action_counts_repo import NavActionCountsRepository
from app.persistence.sqlalchemy.models.config import (
    AppSetting,
    Coupon,
    Language,
    MobileAppConfig,
)
from .conftest import RepoMockSession


@pytest.mark.asyncio
async def test_app_settings_repo_lifecycle():
    now = datetime.now(timezone.utc)
    setting = AppSetting(id="settings", data={"site_name": "Zemen Services"}, updated_at=now)
    session = RepoMockSession(scalar_one_or_none_value=setting, scalars_value=[setting])
    repo = AppSettingsRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(setting)
    assert domain.id == "settings"
    assert domain.data["site_name"] == "Zemen Services"

    all_settings = await repo.list_all_settings()
    assert len(all_settings) == 1
    assert all_settings[0].id == "settings"

    by_id = await repo.get_setting_by_id("settings")
    assert by_id is not None
    assert by_id.id == "settings"

    upserted = await repo.upsert_setting("settings", {"site_name": "Updated Zemen"})
    assert upserted.id == "settings"


@pytest.mark.asyncio
async def test_language_repo_lifecycle():
    lid = uuid4()
    lang = Language(id=lid, code="am", name="Amharic", active=True)
    session = RepoMockSession(scalar_one_or_none_value=lang, scalars_value=[lang])
    repo = LanguageRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(lang)
    assert domain.id == lid
    assert domain.code == "am"
    assert domain.name == "Amharic"

    languages = await repo.list_languages()
    assert len(languages) == 1
    assert languages[0].code == "am"

    upserted = await repo.upsert_language(id=lid, code="am", name="Amharic", active=True)
    assert upserted.id == lid

    deleted = await repo.delete_language(lid)
    assert deleted is True

    bulk_del = await repo.delete_languages([lid])
    assert bulk_del >= 0


@pytest.mark.asyncio
async def test_mobile_app_config_repo_lifecycle():
    now = datetime.now(timezone.utc)
    cfg = MobileAppConfig(
        app_key="customer_app",
        maintenance_mode=False,
        maintenance_message="Under maintenance",
        maintenance_affected_versions=[],
        update_needed=True,
        update_message="Please update",
        update_affected_versions=[],
        created_at=now,
        updated_at=now,
    )
    session = RepoMockSession(scalar_one_or_none_value=cfg, scalars_value=[cfg])
    repo = MobileAppConfigRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(cfg)
    assert domain.app_key == "customer_app"
    assert domain.update_needed is True

    configs = await repo.list_configs()
    assert len(configs) == 1
    assert configs[0].app_key == "customer_app"

    by_key = await repo.get_by_app_key("customer_app")
    assert by_key is not None

    updated = await repo.update_config("customer_app", {"maintenance_mode": True})
    assert updated is not None


@pytest.mark.asyncio
async def test_coupon_repo_lifecycle():
    now = datetime.now(timezone.utc)
    coupon = Coupon(
        id=1,
        title="Welcome 2026",
        code="WELCOME2026",
        amount=Decimal("100.00"),
        min_amount=Decimal("500.00"),
        active=True,
        is_private=False,
        is_fix=True,
        expired_at=now,
        created_at=now,
    )
    session = RepoMockSession(scalar_one_or_none_value=coupon, scalars_value=[coupon])
    repo = CouponRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(coupon)
    assert domain.id == 1
    assert domain.code == "WELCOME2026"
    assert domain.amount == Decimal("100.00")

    coupons = await repo.list_coupons()
    assert len(coupons) == 1

    by_id = await repo.get_coupon_by_id(1)
    assert by_id is not None

    by_code = await repo.get_by_code("WELCOME2026")
    assert by_code is not None

    updated = await repo.update_coupon(1, {"active": False})
    assert updated is not None

    deleted = await repo.delete_coupon(1)
    assert deleted is True


@pytest.mark.asyncio
async def test_nav_action_counts_repo():
    session = RepoMockSession(scalar_one_or_none_value=7)
    repo = NavActionCountsRepository(session)

    counts = await repo.get_aggregated_counts()
    assert counts.payout_requests == 1  # RepoMockSession returns 1 on "count("
    assert counts.verify_documents == 1
    assert counts.approve_services == 1
    assert counts.bookings == 1
    assert counts.job_requests == 1
    assert counts.total == 5
    assert counts.to_dict()["/admin/verify-documents"] == 1
