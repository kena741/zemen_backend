from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.config import (
    AppSettingOut,
    BannerOut,
    CountryTaxOut,
    CouponOut,
    CurrencyOut,
    LanguageOut,
    MobileAppConfigOut,
)
from app.core.services import config_service
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/config", tags=["Config"])


@router.get("/banners", response_model=list[BannerOut], operation_id="config_list_banners")
async def list_banners(
    db: Annotated[AsyncSession, Depends(get_db)],
    active_only: bool = Query(True, alias="activeOnly"),
) -> list[BannerOut]:
    rows = await config_service.list_banners(db, active_only=active_only)
    return [BannerOut.model_validate(r) for r in rows]


@router.get("/taxes", response_model=list[CountryTaxOut], operation_id="config_list_taxes")
async def list_taxes(
    db: Annotated[AsyncSession, Depends(get_db)],
    active_only: bool = Query(True, alias="activeOnly"),
) -> list[CountryTaxOut]:
    rows = await config_service.list_taxes(db, active_only=active_only)
    return [CountryTaxOut.model_validate(r) for r in rows]


@router.get("/coupons", response_model=list[CouponOut], operation_id="config_list_coupons")
async def list_coupons(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CouponOut]:
    rows = await config_service.list_coupons(db, public_only=True)
    return [CouponOut.model_validate(r) for r in rows]


@router.get("/currencies", response_model=list[CurrencyOut], operation_id="config_list_currencies")
async def list_currencies(
    db: Annotated[AsyncSession, Depends(get_db)],
    active_only: bool = Query(True, alias="activeOnly"),
) -> list[CurrencyOut]:
    rows = await config_service.list_currencies(db, active_only=active_only)
    return [CurrencyOut.model_validate(r) for r in rows]


@router.get(
    "/currency",
    response_model=CurrencyOut | None,
    operation_id="config_get_active_currency",
    summary="The active currency, or null when none is configured",
)
async def get_active_currency(db: Annotated[AsyncSession, Depends(get_db)]) -> CurrencyOut | None:
    row = await config_service.get_active_currency(db)
    return CurrencyOut.model_validate(row) if row else None


@router.get("/languages", response_model=list[LanguageOut], operation_id="config_list_languages")
async def list_languages(
    db: Annotated[AsyncSession, Depends(get_db)],
    active_only: bool = Query(False, alias="activeOnly"),
) -> list[LanguageOut]:
    rows = await config_service.list_languages(db, active_only=active_only)
    return [LanguageOut.model_validate(r) for r in rows]


@router.get(
    "/settings/{setting_id}",
    response_model=AppSettingOut,
    operation_id="config_get_setting",
)
async def get_setting(
    setting_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AppSettingOut:
    row = await config_service.get_app_setting(db, setting_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found")
    return AppSettingOut.model_validate(row)


@router.get(
    "/mobile/{app_key}",
    response_model=MobileAppConfigOut,
    operation_id="config_get_mobile",
)
async def get_mobile_config(
    app_key: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MobileAppConfigOut:
    row = await config_service.get_mobile_config(db, app_key)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    return MobileAppConfigOut.model_validate(row)
