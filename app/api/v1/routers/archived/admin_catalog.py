"""Admin CRUD replacing lolelink-admin browser writes (Plan 6b).

Permissions mirror lolelink-admin `canAccessAdminRoute` (page group + `:write`).
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.admin import AdminServiceOut
from app.api.v1.schemas.admin_catalog import (
    AdminCouponOut,
    AdminHandymanCreate,
    AdminHandymanOut,
    AdminHandymanPatch,
    AdminServiceCreate,
    AdminServiceWrite,
    AdminSubCategoryOut,
    AdminTaxOut,
    CategoryCreate,
    CategoryPatch,
    CouponCreate,
    CouponPatch,
    NotificationBulkResult,
    NotificationIdsBody,
    SubCategoryCreate,
    SubCategoryPatch,
    TaxCreate,
    TaxPatch,
)
from app.api.v1.schemas.catalog import CategoryOut
from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.notification import NotificationOut
from app.core.security.admin_deps import AdminContext, require_admin_permission
from app.core.services import admin_catalog
from app.core.services.admin_catalog import AdminConflict
from app.persistence.sqlalchemy.deps import get_db
from app.persistence.sqlalchemy.models import (
    Category,
    CountryTax,
    Coupon,
    Handyman,
    Notification,
    Service,
    SubCategory,
)

router = APIRouter(prefix="/admin", tags=["Admin"])

Db = Annotated[AsyncSession, Depends(get_db)]


def _perm(p: str):
    return Annotated[AdminContext, Depends(require_admin_permission(p))]


CatalogRead = _perm("catalog:read")
CatalogWrite = _perm("catalog:write")
FinanceRead = _perm("finance:read")
FinanceWrite = _perm("finance:write")
ProvidersRead = _perm("providers:read")
ProvidersWrite = _perm("providers:write")
NotificationsRead = _perm("notifications:read")
NotificationsWrite = _perm("notifications:write")
ServicesWrite = _perm("services:write")


async def _get_or_404(db: AsyncSession, model: Any, ident: Any, label: str) -> Any:
    row = (await db.execute(select(model).where(model.id == ident).with_for_update())).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found")
    return row


def _conflict(exc: AdminConflict) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def _patch(body: Any) -> dict[str, Any]:
    return body.model_dump(exclude_unset=True)


# --- Categories -------------------------------------------------------------------------


@router.post("/categories", response_model=CategoryOut, status_code=201, operation_id="admin_create_category")
async def admin_create_category(body: CategoryCreate, ctx: CatalogWrite, db: Db) -> CategoryOut:
    return CategoryOut.model_validate(await admin_catalog.create_category(db, ctx, body.model_dump()))


@router.patch("/categories/{category_id}", response_model=CategoryOut, operation_id="admin_update_category")
async def admin_update_category(category_id: UUID, body: CategoryPatch, ctx: CatalogWrite, db: Db) -> CategoryOut:
    row = await _get_or_404(db, Category, category_id, "Category")
    return CategoryOut.model_validate(await admin_catalog.update_category(db, ctx, row, _patch(body)))


@router.delete("/categories/{category_id}", status_code=204, operation_id="admin_delete_category")
async def admin_delete_category(category_id: UUID, ctx: CatalogWrite, db: Db) -> Response:
    row = await _get_or_404(db, Category, category_id, "Category")
    try:
        await admin_catalog.delete_category(db, ctx, row)
    except AdminConflict as exc:
        raise _conflict(exc) from exc
    return Response(status_code=204)


# --- Sub-categories ---------------------------------------------------------------------


async def _subcategory_out(db: AsyncSession, row: SubCategory) -> AdminSubCategoryOut:
    out = AdminSubCategoryOut.model_validate(row)
    return out.model_copy(update={"document_ids": await admin_catalog.subcategory_document_ids(db, row.id)})


@router.get(
    "/subcategories/{sub_category_id}",
    response_model=AdminSubCategoryOut,
    operation_id="admin_get_subcategory",
    summary="Sub-category with its required-document ids",
)
async def admin_get_subcategory(sub_category_id: UUID, _ctx: CatalogRead, db: Db) -> AdminSubCategoryOut:
    row = (await db.execute(select(SubCategory).where(SubCategory.id == sub_category_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category not found")
    return await _subcategory_out(db, row)


@router.post(
    "/subcategories", response_model=AdminSubCategoryOut, status_code=201, operation_id="admin_create_subcategory"
)
async def admin_create_subcategory(body: SubCategoryCreate, ctx: CatalogWrite, db: Db) -> AdminSubCategoryOut:
    try:
        row = await admin_catalog.create_subcategory(db, ctx, body.model_dump())
    except AdminConflict as exc:
        raise _conflict(exc) from exc
    return await _subcategory_out(db, row)


@router.patch(
    "/subcategories/{sub_category_id}", response_model=AdminSubCategoryOut, operation_id="admin_update_subcategory"
)
async def admin_update_subcategory(
    sub_category_id: UUID, body: SubCategoryPatch, ctx: CatalogWrite, db: Db
) -> AdminSubCategoryOut:
    row = await _get_or_404(db, SubCategory, sub_category_id, "Sub-category")
    try:
        row = await admin_catalog.update_subcategory(db, ctx, row, _patch(body))
    except AdminConflict as exc:
        raise _conflict(exc) from exc
    return await _subcategory_out(db, row)


@router.delete("/subcategories/{sub_category_id}", status_code=204, operation_id="admin_delete_subcategory")
async def admin_delete_subcategory(sub_category_id: UUID, ctx: CatalogWrite, db: Db) -> Response:
    row = await _get_or_404(db, SubCategory, sub_category_id, "Sub-category")
    try:
        await admin_catalog.delete_subcategory(db, ctx, row)
    except AdminConflict as exc:
        raise _conflict(exc) from exc
    return Response(status_code=204)


# --- Coupons ----------------------------------------------------------------------------


@router.get("/coupons", response_model=list[AdminCouponOut], operation_id="admin_list_coupons")
async def admin_list_coupons(_ctx: CatalogRead, db: Db) -> list[AdminCouponOut]:
    rows = (await db.execute(select(Coupon).order_by(Coupon.created_at.desc()))).scalars()
    return [AdminCouponOut.model_validate(r) for r in rows]


@router.post("/coupons", response_model=AdminCouponOut, status_code=201, operation_id="admin_create_coupon")
async def admin_create_coupon(body: CouponCreate, ctx: CatalogWrite, db: Db) -> AdminCouponOut:
    return AdminCouponOut.model_validate(await admin_catalog.create_coupon(db, ctx, body.model_dump()))


@router.patch("/coupons/{coupon_id}", response_model=AdminCouponOut, operation_id="admin_update_coupon")
async def admin_update_coupon(coupon_id: int, body: CouponPatch, ctx: CatalogWrite, db: Db) -> AdminCouponOut:
    row = await _get_or_404(db, Coupon, coupon_id, "Coupon")
    return AdminCouponOut.model_validate(await admin_catalog.update_coupon(db, ctx, row, _patch(body)))


@router.delete("/coupons/{coupon_id}", status_code=204, operation_id="admin_delete_coupon")
async def admin_delete_coupon(coupon_id: int, ctx: CatalogWrite, db: Db) -> Response:
    row = await _get_or_404(db, Coupon, coupon_id, "Coupon")
    try:
        await admin_catalog.delete_coupon(db, ctx, row)
    except AdminConflict as exc:
        raise _conflict(exc) from exc
    return Response(status_code=204)


# --- Country taxes ----------------------------------------------------------------------


@router.get("/taxes", response_model=list[AdminTaxOut], operation_id="admin_list_taxes")
async def admin_list_taxes(_ctx: FinanceRead, db: Db) -> list[AdminTaxOut]:
    rows = (await db.execute(select(CountryTax).order_by(CountryTax.created_at.desc()))).scalars()
    return [AdminTaxOut.model_validate(r) for r in rows]


@router.post("/taxes", response_model=AdminTaxOut, status_code=201, operation_id="admin_create_tax")
async def admin_create_tax(body: TaxCreate, ctx: FinanceWrite, db: Db) -> AdminTaxOut:
    return AdminTaxOut.model_validate(await admin_catalog.create_tax(db, ctx, body.model_dump()))


@router.patch("/taxes/{tax_id}", response_model=AdminTaxOut, operation_id="admin_update_tax")
async def admin_update_tax(tax_id: int, body: TaxPatch, ctx: FinanceWrite, db: Db) -> AdminTaxOut:
    row = await _get_or_404(db, CountryTax, tax_id, "Tax")
    return AdminTaxOut.model_validate(await admin_catalog.update_tax(db, ctx, row, _patch(body)))


@router.delete("/taxes/{tax_id}", status_code=204, operation_id="admin_delete_tax")
async def admin_delete_tax(tax_id: int, ctx: FinanceWrite, db: Db) -> Response:
    row = await _get_or_404(db, CountryTax, tax_id, "Tax")
    try:
        await admin_catalog.delete_tax(db, ctx, row)
    except AdminConflict as exc:
        raise _conflict(exc) from exc
    return Response(status_code=204)


# --- Handymen ---------------------------------------------------------------------------


@router.get("/handymen", response_model=Page[AdminHandymanOut], operation_id="admin_list_handymen")
async def admin_list_handymen(
    _ctx: ProvidersRead,
    db: Db,
    provider_id: UUID | None = Query(None, alias="providerId"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Page[AdminHandymanOut]:
    stmt = select(Handyman)
    if provider_id is not None:
        stmt = stmt.where(Handyman.provider_id == provider_id)
    stmt = stmt.order_by(Handyman.created_at.desc().nulls_last()).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars()
    return Page(items=[AdminHandymanOut.model_validate(r) for r in rows], meta=PageMeta(limit=limit, offset=offset))


@router.post("/handymen", response_model=AdminHandymanOut, status_code=201, operation_id="admin_create_handyman")
async def admin_create_handyman(body: AdminHandymanCreate, ctx: ProvidersWrite, db: Db) -> AdminHandymanOut:
    try:
        row = await admin_catalog.create_handyman(db, ctx, body.model_dump())
    except AdminConflict as exc:
        raise _conflict(exc) from exc
    return AdminHandymanOut.model_validate(row)


@router.patch("/handymen/{handyman_id}", response_model=AdminHandymanOut, operation_id="admin_update_handyman")
async def admin_update_handyman(
    handyman_id: UUID, body: AdminHandymanPatch, ctx: ProvidersWrite, db: Db
) -> AdminHandymanOut:
    row = await _get_or_404(db, Handyman, handyman_id, "Handyman")
    try:
        row = await admin_catalog.update_handyman(db, ctx, row, _patch(body))
    except AdminConflict as exc:
        raise _conflict(exc) from exc
    return AdminHandymanOut.model_validate(row)


@router.delete("/handymen/{handyman_id}", status_code=204, operation_id="admin_delete_handyman")
async def admin_delete_handyman(handyman_id: UUID, ctx: ProvidersWrite, db: Db) -> Response:
    row = await _get_or_404(db, Handyman, handyman_id, "Handyman")
    try:
        await admin_catalog.delete_handyman(db, ctx, row)
    except AdminConflict as exc:
        raise _conflict(exc) from exc
    return Response(status_code=204)


# --- Admin notifications ----------------------------------------------------------------


@router.get("/notifications", response_model=list[NotificationOut], operation_id="admin_list_notifications")
async def admin_list_notifications(
    _ctx: NotificationsRead,
    db: Db,
    limit: int = Query(100, ge=1, le=500),
    unread_only: bool = Query(False, alias="unreadOnly"),
) -> list[NotificationOut]:
    stmt = select(Notification).where(Notification.recipient_role == "admin")
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc().nulls_last()).limit(limit)
    return [NotificationOut.model_validate(r) for r in (await db.execute(stmt)).scalars()]


@router.post(
    "/notifications/read",
    response_model=NotificationBulkResult,
    operation_id="admin_mark_notifications_read",
    summary="Mark admin notifications read (given ids, or all unread when ids is omitted)",
)
async def admin_mark_notifications_read(
    body: NotificationIdsBody, ctx: NotificationsWrite, db: Db
) -> NotificationBulkResult:
    ids, read_at = await admin_catalog.mark_notifications_read(db, ctx, body.ids)
    return NotificationBulkResult(ids=ids, read_at=read_at)


@router.post(
    "/notifications/delete",
    response_model=NotificationBulkResult,
    operation_id="admin_delete_notifications",
    summary="Delete admin notifications by id",
)
async def admin_delete_notifications(
    body: NotificationIdsBody, ctx: NotificationsWrite, db: Db
) -> NotificationBulkResult:
    if not body.ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="ids is required")
    return NotificationBulkResult(ids=await admin_catalog.delete_notifications(db, ctx, body.ids))


# --- Services ---------------------------------------------------------------------------


@router.post("/services", response_model=AdminServiceOut, status_code=201, operation_id="admin_create_service")
async def admin_create_service(body: AdminServiceCreate, ctx: ServicesWrite, db: Db) -> AdminServiceOut:
    try:
        row = await admin_catalog.create_service(db, ctx, body.model_dump())
    except AdminConflict as exc:
        raise _conflict(exc) from exc
    return AdminServiceOut.model_validate(row)


@router.patch("/services/{service_id}", response_model=AdminServiceOut, operation_id="admin_update_service")
async def admin_update_service(
    service_id: UUID, body: AdminServiceWrite, ctx: ServicesWrite, db: Db
) -> AdminServiceOut:
    row = await _get_or_404(db, Service, service_id, "Service")
    try:
        row = await admin_catalog.update_service(db, ctx, row, _patch(body))
    except AdminConflict as exc:
        raise _conflict(exc) from exc
    return AdminServiceOut.model_validate(row)


@router.post(
    "/services/{service_id}/archive",
    response_model=AdminServiceOut,
    operation_id="admin_archive_service",
    summary="Soft-delete a service (isArchived=true, status=false, active=false)",
)
async def admin_archive_service(service_id: UUID, ctx: ServicesWrite, db: Db) -> AdminServiceOut:
    row = await _get_or_404(db, Service, service_id, "Service")
    return AdminServiceOut.model_validate(await admin_catalog.archive_service(db, ctx, row))
