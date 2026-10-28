from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import (
    AppSetting,
    Banner,
    CountryTax,
    Coupon,
    Currency,
    Language,
    MobileAppConfig,
)


async def list_banners(db: AsyncSession, *, active_only: bool = True) -> list[Banner]:
    stmt = select(Banner).order_by(Banner.id)
    if active_only:
        stmt = stmt.where(Banner.active.is_(True))
    return list((await db.execute(stmt)).scalars().all())


async def list_taxes(db: AsyncSession, *, active_only: bool = True) -> list[CountryTax]:
    stmt = select(CountryTax).order_by(CountryTax.id)
    if active_only:
        stmt = stmt.where(CountryTax.active.is_(True))
    return list((await db.execute(stmt)).scalars().all())


async def list_coupons(db: AsyncSession, *, public_only: bool = True) -> list[Coupon]:
    stmt = select(Coupon).where(Coupon.active.is_(True)).order_by(Coupon.id)
    if public_only:
        stmt = stmt.where(Coupon.is_private.is_not(True))
    return list((await db.execute(stmt)).scalars().all())


async def list_currencies(db: AsyncSession, *, active_only: bool = True) -> list[Currency]:
    stmt = select(Currency).order_by(Currency.id)
    if active_only:
        stmt = stmt.where(Currency.active.is_(True))
    return list((await db.execute(stmt)).scalars().all())


async def get_active_currency(db: AsyncSession) -> Currency | None:
    stmt = select(Currency).where(Currency.active.is_(True)).order_by(Currency.id).limit(1)
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_languages(db: AsyncSession, *, active_only: bool = False) -> list[Language]:
    stmt = select(Language).order_by(Language.name)
    if active_only:
        stmt = stmt.where(Language.active.is_(True))
    return list((await db.execute(stmt)).scalars().all())


_SECRET_MARKERS = ("secret", "private", "password", "token", "servicerole", "apikey", "webhook")


def _is_secret_key(key: str) -> bool:
    k = key.lower().replace("_", "").replace("-", "")
    return any(m in k for m in _SECRET_MARKERS)


def redact_secrets(value: Any) -> Any:
    """Copy of `value` without secret fields. `app_settings.payment` stores the live Chapa secret key."""
    if isinstance(value, dict):
        return {k: redact_secrets(v) for k, v in value.items() if not _is_secret_key(str(k))}
    if isinstance(value, list):
        return [redact_secrets(v) for v in value]
    return value


async def get_app_setting(db: AsyncSession, setting_id: str) -> dict[str, Any] | None:
    row = (
        await db.execute(select(AppSetting).where(AppSetting.id == setting_id))
    ).scalar_one_or_none()
    if row is None:
        return None
    return {"id": row.id, "data": redact_secrets(row.data or {}), "updated_at": row.updated_at}


async def get_mobile_config(db: AsyncSession, app_key: str) -> MobileAppConfig | None:
    return (
        await db.execute(select(MobileAppConfig).where(MobileAppConfig.app_key == app_key))
    ).scalar_one_or_none()
