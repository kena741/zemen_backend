"""Admin Platform Configuration, Settings, Mobile App Config, Coupons, and Nav Action Counts API router."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.admin.requests.settings import (
    CouponCreateRequest,
    CouponUpdateRequest,
    LanguageBulkMutateRequest,
    MobileAppConfigPatchRequest,
    SettingsUpdateRequest,
)
from app.api.v1.schemas.admin.responses.settings import (
    CouponListResponse,
    CouponResponseItem,
    CouponSingleResponse,
    MobileAppConfigListResponse,
    MobileAppConfigResponseItem,
    MobileAppConfigSingleResponse,
    NavActionCountsResponse,
    SettingsDataResponse,
    SettingsUpdateResponse,
)
from app.core.security.admin_deps import (
    AdminContext,
    get_admin_context,
    require_admin_permission,
)
from app.core.services.admin.audit_service import AdminAuditService
from app.core.services.admin.settings_service import SettingsAdminService
from app.persistence.repositories.activity_log_repo import ActivityLogRepository
from app.persistence.repositories.app_settings_repo import AppSettingsRepository
from app.persistence.repositories.coupon_repo import CouponRepository
from app.persistence.repositories.language_repo import LanguageRepository
from app.persistence.repositories.mobile_app_config_repo import MobileAppConfigRepository
from app.persistence.repositories.nav_action_counts_repo import NavActionCountsRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(tags=["admin-settings"])

Db = Annotated[AsyncSession, Depends(get_db)]
RequireAdmin = Annotated[AdminContext, Depends(get_admin_context)]
CanReadSettings = Annotated[AdminContext, Depends(require_admin_permission("settings:read"))]
CanWriteSettings = Annotated[AdminContext, Depends(require_admin_permission("settings:write"))]
CanReadCatalog = Annotated[AdminContext, Depends(require_admin_permission("catalog:read"))]
CanWriteCatalog = Annotated[AdminContext, Depends(require_admin_permission("catalog:write"))]


def _get_settings_service(db: AsyncSession) -> SettingsAdminService:
    app_settings_repo = AppSettingsRepository(db)
    language_repo = LanguageRepository(db)
    mobile_config_repo = MobileAppConfigRepository(db)
    coupon_repo = CouponRepository(db)
    nav_action_counts_repo = NavActionCountsRepository(db)
    audit_repo = ActivityLogRepository(db)
    audit_service = AdminAuditService(audit_repo)

    return SettingsAdminService(
        app_settings_repo=app_settings_repo,
        language_repo=language_repo,
        mobile_config_repo=mobile_config_repo,
        coupon_repo=coupon_repo,
        nav_action_counts_repo=nav_action_counts_repo,
        audit_service=audit_service,
    )


# --- Platform App Settings ---------------------------------------------------


@router.get(
    "/admin/settings",
    response_model=SettingsDataResponse,
    operation_id="admin_settings_get",
    summary="Fetch all app settings and active languages",
)
@router.get("/settings", response_model=SettingsDataResponse, include_in_schema=False)
async def get_settings(_: CanReadSettings, db: Db) -> SettingsDataResponse:
    service = _get_settings_service(db)
    data = await service.get_settings()
    return SettingsDataResponse.model_validate(data)


@router.post(
    "/admin/settings",
    response_model=SettingsUpdateResponse,
    operation_id="admin_settings_update",
    summary="Update multiple platform configuration sections",
)
@router.post("/settings", response_model=SettingsUpdateResponse, include_in_schema=False)
async def update_settings(
    body: SettingsUpdateRequest,
    ctx: CanWriteSettings,
    db: Db,
) -> SettingsUpdateResponse:
    service = _get_settings_service(db)
    payload = body.model_dump(exclude_unset=True)
    res = await service.update_settings(payload=payload, ctx=ctx)
    return SettingsUpdateResponse(data=res)


@router.post(
    "/settings/languages",
    status_code=status.HTTP_200_OK,
    operation_id="admin_languages_bulk_mutate",
    summary="Bulk mutate languages (upsert/delete)",
)
@router.post("/admin/settings/languages", status_code=status.HTTP_200_OK, include_in_schema=False)
async def bulk_mutate_languages(
    body: LanguageBulkMutateRequest,
    ctx: CanWriteSettings,
    db: Db,
) -> dict[str, bool]:
    service = _get_settings_service(db)
    await service.bulk_mutate_languages(
        upserts=body.upserts,
        inserts=body.inserts,
        delete_ids=body.delete_ids,
        ctx=ctx,
    )
    return {"ok": True}


# --- Mobile App Config -------------------------------------------------------


@router.get(
    "/admin/mobile-app-config",
    response_model=MobileAppConfigListResponse,
    operation_id="admin_mobile_config_list",
    summary="List mobile app configs for all apps",
)
@router.get("/mobile-app-config", response_model=MobileAppConfigListResponse, include_in_schema=False)
async def list_mobile_app_configs(_: CanReadSettings, db: Db) -> MobileAppConfigListResponse:
    service = _get_settings_service(db)
    configs = await service.list_mobile_app_configs()
    return MobileAppConfigListResponse(
        data=[MobileAppConfigResponseItem.model_validate(c) for c in configs]
    )


@router.patch(
    "/admin/mobile-app-config",
    response_model=MobileAppConfigSingleResponse,
    operation_id="admin_mobile_config_update",
    summary="Update mobile app maintenance mode and force update config",
)
@router.patch("/mobile-app-config", response_model=MobileAppConfigSingleResponse, include_in_schema=False)
async def update_mobile_app_config(
    body: MobileAppConfigPatchRequest,
    ctx: CanWriteSettings,
    db: Db,
) -> MobileAppConfigSingleResponse:
    service = _get_settings_service(db)
    updates = body.model_dump(exclude_unset=True, exclude={"app_key"})
    cfg = await service.update_mobile_app_config(
        app_key=body.app_key,
        updates=updates,
        ctx=ctx,
    )
    return MobileAppConfigSingleResponse(data=MobileAppConfigResponseItem.model_validate(cfg))


# --- Nav Action Counts -------------------------------------------------------


@router.get(
    "/admin/nav-action-counts",
    response_model=NavActionCountsResponse,
    operation_id="admin_nav_action_counts",
    summary="Aggregate pending action counts across all operational buckets",
)
async def get_nav_action_counts(
    _: RequireAdmin,
    db: Db,
) -> NavActionCountsResponse:
    service = _get_settings_service(db)
    domain_counts = await service.get_nav_action_counts()
    return NavActionCountsResponse(counts=domain_counts.to_dict())


# --- Coupons -----------------------------------------------------------------


@router.get(
    "/admin/coupons",
    response_model=CouponListResponse,
    operation_id="admin_coupons_list",
    summary="List all promotional coupons",
)
async def list_coupons(_: CanReadCatalog, db: Db) -> CouponListResponse:
    service = _get_settings_service(db)
    coupons = await service.list_coupons()
    return CouponListResponse(data=[CouponResponseItem.model_validate(c) for c in coupons])


@router.post(
    "/admin/coupons",
    response_model=CouponSingleResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_coupons_create",
    summary="Create a new promotional coupon",
)
async def create_coupon(
    body: CouponCreateRequest,
    ctx: CanWriteCatalog,
    db: Db,
) -> CouponSingleResponse:
    service = _get_settings_service(db)
    created = await service.create_coupon(data=body.model_dump(), ctx=ctx)
    return CouponSingleResponse(data=CouponResponseItem.model_validate(created))


@router.patch(
    "/admin/coupons/{coupon_id}",
    response_model=CouponSingleResponse,
    operation_id="admin_coupons_update_path",
    summary="Update coupon by ID",
)
async def update_coupon(
    coupon_id: int,
    body: CouponUpdateRequest,
    ctx: CanWriteCatalog,
    db: Db,
) -> CouponSingleResponse:
    service = _get_settings_service(db)
    updated = await service.update_coupon(
        coupon_id=coupon_id,
        updates=body.model_dump(exclude_unset=True, exclude={"id"}),
        ctx=ctx,
    )
    return CouponSingleResponse(data=CouponResponseItem.model_validate(updated))


@router.delete(
    "/admin/coupons/{coupon_id}",
    status_code=status.HTTP_200_OK,
    operation_id="admin_coupons_delete",
    summary="Delete coupon by ID",
)
async def delete_coupon(
    coupon_id: int,
    ctx: CanWriteCatalog,
    db: Db,
) -> dict[str, bool]:
    service = _get_settings_service(db)
    await service.delete_coupon(coupon_id=coupon_id, ctx=ctx)
    return {"ok": True}
