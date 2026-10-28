"""Admin CRUD for catalog/config tables lolelink-admin currently writes from the browser.

Every mutation records an `admin_activity_log` row in the same transaction.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.admin_deps import AdminContext
from app.core.services.admin_audit import log_admin_activity
from app.persistence.sqlalchemy.models import (
    Category,
    CountryTax,
    Coupon,
    Document,
    Handyman,
    Notification,
    Provider,
    Service,
    SubCategory,
    SubCategoryDocument,
)


class AdminConflict(Exception):
    """Write rejected because of referenced rows or invalid references."""


def _jsonable(value: Any) -> Any:
    if isinstance(value, (UUID, Decimal, datetime)):
        return str(value)
    return value


def apply_patch(row: Any, patch: dict[str, Any], *, non_nullable: frozenset[str]) -> dict[str, Any]:
    """Set changed attributes on `row`; returns {field: {from, to}} for the audit log.

    `None` is ignored for non-nullable columns so a partial client payload cannot
    null out required data.
    """
    changes: dict[str, Any] = {}
    for key, value in patch.items():
        if value is None and key in non_nullable:
            continue
        old = getattr(row, key)
        if old == value:
            continue
        setattr(row, key, value)
        changes[key] = {"from": _jsonable(old), "to": _jsonable(value)}
    return changes


async def _delete_or_conflict(db: AsyncSession, row: Any, message: str) -> None:
    try:
        async with db.begin_nested():
            await db.delete(row)
            await db.flush()
    except IntegrityError as exc:
        raise AdminConflict(message) from exc


async def _require_exists(db: AsyncSession, model: Any, ident: Any, label: str) -> None:
    if ident is None:
        return
    if (await db.execute(select(model.id).where(model.id == ident))).first() is None:
        raise AdminConflict(f"{label} {ident} does not exist")


# --- Categories -------------------------------------------------------------------------

_CATEGORY_REQUIRED = frozenset({"category_name"})


async def create_category(db: AsyncSession, ctx: AdminContext, data: dict[str, Any]) -> Category:
    row = Category(id=uuid4(), **data)
    db.add(row)
    await db.flush()
    await log_admin_activity(
        db, ctx, action="create", resource_type="settings", resource_id=row.id,
        summary=f"Created category {row.category_name}", metadata={"kind": "category"},
    )
    return row


async def update_category(db: AsyncSession, ctx: AdminContext, row: Category, patch: dict[str, Any]) -> Category:
    changes = apply_patch(row, patch, non_nullable=_CATEGORY_REQUIRED)
    if changes:
        await db.flush()
        await log_admin_activity(
            db, ctx, action="update", resource_type="settings", resource_id=row.id,
            summary=f"Updated category {row.category_name}", metadata={"kind": "category", "changes": changes},
        )
    return row


async def delete_category(db: AsyncSession, ctx: AdminContext, row: Category) -> None:
    name = row.category_name
    rid = row.id
    await _delete_or_conflict(
        db, row, "Category is still used by sub-categories or services; reassign them first."
    )
    await log_admin_activity(
        db, ctx, action="delete", resource_type="settings", resource_id=rid,
        summary=f"Deleted category {name}", metadata={"kind": "category"},
    )


# --- Sub-categories (+ required-document links) -----------------------------------------

_SUBCATEGORY_REQUIRED = frozenset({"sub_category_name", "category_id", "is_free"})


async def subcategory_document_ids(db: AsyncSession, sub_category_id: UUID) -> list[UUID]:
    return list(
        (
            await db.execute(
                select(SubCategoryDocument.document_id).where(
                    SubCategoryDocument.sub_category_id == sub_category_id
                )
            )
        ).scalars()
    )


async def _replace_document_links(db: AsyncSession, sub_category_id: UUID, document_ids: list[UUID]) -> None:
    unique = list(dict.fromkeys(document_ids))
    if unique:
        found = set((await db.execute(select(Document.id).where(Document.id.in_(unique)))).scalars())
        missing = [str(d) for d in unique if d not in found]
        if missing:
            raise AdminConflict(f"Unknown document ids: {', '.join(missing)}")
    await db.execute(
        delete(SubCategoryDocument).where(SubCategoryDocument.sub_category_id == sub_category_id)
    )
    for document_id in unique:
        db.add(SubCategoryDocument(id=uuid4(), sub_category_id=sub_category_id, document_id=document_id))
    await db.flush()


async def create_subcategory(db: AsyncSession, ctx: AdminContext, data: dict[str, Any]) -> SubCategory:
    document_ids = data.pop("document_ids", []) or []
    await _require_exists(db, Category, data["category_id"], "Category")
    row = SubCategory(id=uuid4(), **data)
    db.add(row)
    await db.flush()
    if document_ids:
        await _replace_document_links(db, row.id, document_ids)
    await log_admin_activity(
        db, ctx, action="create", resource_type="settings", resource_id=row.id,
        summary=f"Created subcategory {row.sub_category_name}",
        metadata={"kind": "sub_category", "isFree": row.is_free, "documentIds": [str(d) for d in document_ids]},
    )
    return row


async def update_subcategory(
    db: AsyncSession, ctx: AdminContext, row: SubCategory, patch: dict[str, Any]
) -> SubCategory:
    document_ids = patch.pop("document_ids", None)
    if patch.get("category_id") is not None:
        await _require_exists(db, Category, patch["category_id"], "Category")
    changes = apply_patch(row, patch, non_nullable=_SUBCATEGORY_REQUIRED)
    if document_ids is not None:
        before = await subcategory_document_ids(db, row.id)
        await _replace_document_links(db, row.id, document_ids)
        if set(before) != set(document_ids):
            changes["documentIds"] = {
                "from": [str(d) for d in before],
                "to": [str(d) for d in dict.fromkeys(document_ids)],
            }
    if changes:
        await db.flush()
        await log_admin_activity(
            db, ctx, action="update", resource_type="settings", resource_id=row.id,
            summary=f"Updated subcategory {row.sub_category_name}",
            metadata={"kind": "sub_category", "changes": changes},
        )
    return row


async def delete_subcategory(db: AsyncSession, ctx: AdminContext, row: SubCategory) -> None:
    name = row.sub_category_name
    rid = row.id
    await _delete_or_conflict(db, row, "Sub-category is still used by services; reassign them first.")
    await log_admin_activity(
        db, ctx, action="delete", resource_type="settings", resource_id=rid,
        summary=f"Deleted subcategory {name}", metadata={"kind": "sub_category"},
    )


# --- Coupons ----------------------------------------------------------------------------


async def create_coupon(db: AsyncSession, ctx: AdminContext, data: dict[str, Any]) -> Coupon:
    row = Coupon(created_at=datetime.now(UTC), **data)
    db.add(row)
    await db.flush()
    await log_admin_activity(
        db, ctx, action="create", resource_type="coupon", resource_id=row.id,
        summary=f"Created coupon {row.code}", metadata={"amount": _jsonable(row.amount), "isFix": row.is_fix},
    )
    return row


async def update_coupon(db: AsyncSession, ctx: AdminContext, row: Coupon, patch: dict[str, Any]) -> Coupon:
    changes = apply_patch(row, patch, non_nullable=frozenset({"code", "amount"}))
    if changes:
        await db.flush()
        await log_admin_activity(
            db, ctx, action="update", resource_type="coupon", resource_id=row.id,
            summary=f"Updated coupon {row.code}", metadata={"changes": changes},
        )
    return row


async def delete_coupon(db: AsyncSession, ctx: AdminContext, row: Coupon) -> None:
    code = row.code
    rid = row.id
    await _delete_or_conflict(db, row, "Coupon is referenced by other records.")
    await log_admin_activity(
        db, ctx, action="delete", resource_type="coupon", resource_id=rid,
        summary=f"Deleted coupon {code}",
    )


# --- Country taxes ----------------------------------------------------------------------


def _with_is_fix(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("type") is not None:
        data["is_fix"] = data["type"] == "fixed"
    return data


async def create_tax(db: AsyncSession, ctx: AdminContext, data: dict[str, Any]) -> CountryTax:
    row = CountryTax(created_at=datetime.now(UTC), **_with_is_fix(data))
    db.add(row)
    await db.flush()
    await log_admin_activity(
        db, ctx, action="create", resource_type="tax", resource_id=row.id,
        summary=f"Created tax {row.name} ({row.country})",
        metadata={"value": _jsonable(row.value), "type": row.type, "active": row.active},
    )
    return row


async def update_tax(db: AsyncSession, ctx: AdminContext, row: CountryTax, patch: dict[str, Any]) -> CountryTax:
    changes = apply_patch(row, _with_is_fix(patch), non_nullable=frozenset({"country", "name", "value", "type"}))
    if changes:
        await db.flush()
        await log_admin_activity(
            db, ctx, action="update", resource_type="tax", resource_id=row.id,
            summary=f"Updated tax {row.name} ({row.country})", metadata={"changes": changes},
        )
    return row


async def delete_tax(db: AsyncSession, ctx: AdminContext, row: CountryTax) -> None:
    label = f"{row.name} ({row.country})"
    rid = row.id
    await _delete_or_conflict(db, row, "Tax is referenced by other records.")
    await log_admin_activity(
        db, ctx, action="delete", resource_type="tax", resource_id=rid, summary=f"Deleted tax {label}",
    )


# --- Handymen ---------------------------------------------------------------------------


def _handyman_label(row: Handyman) -> str:
    return " ".join(p for p in (row.first_name, row.last_name) if p) or str(row.id)


async def create_handyman(db: AsyncSession, ctx: AdminContext, data: dict[str, Any]) -> Handyman:
    await _require_exists(db, Provider, data["provider_id"], "Provider")
    row = Handyman(id=uuid4(), created_at=datetime.now(UTC), **data)
    db.add(row)
    await db.flush()
    await log_admin_activity(
        db, ctx, action="create", resource_type="handyman", resource_id=row.id,
        summary=f"Created handyman {_handyman_label(row)}", metadata={"provider_id": str(row.provider_id)},
    )
    return row


async def update_handyman(db: AsyncSession, ctx: AdminContext, row: Handyman, patch: dict[str, Any]) -> Handyman:
    if patch.get("provider_id") is not None:
        await _require_exists(db, Provider, patch["provider_id"], "Provider")
    changes = apply_patch(row, patch, non_nullable=frozenset({"provider_id"}))
    if changes:
        await db.flush()
        await log_admin_activity(
            db, ctx, action="update", resource_type="handyman", resource_id=row.id,
            summary=f"Updated handyman {_handyman_label(row)}", metadata={"changes": changes},
        )
    return row


async def delete_handyman(db: AsyncSession, ctx: AdminContext, row: Handyman) -> None:
    label = _handyman_label(row)
    rid = row.id
    await _delete_or_conflict(
        db, row, "Handyman is assigned to bookings or notifications; deactivate instead."
    )
    await log_admin_activity(
        db, ctx, action="delete", resource_type="handyman", resource_id=rid,
        summary=f"Deleted handyman {label}",
    )


# --- Admin notifications (recipient_role = 'admin' only) --------------------------------

_ADMIN_INBOX = Notification.recipient_role == "admin"


async def mark_notifications_read(
    db: AsyncSession, ctx: AdminContext, ids: list[UUID] | None
) -> tuple[list[UUID], datetime]:
    read_at = datetime.now(UTC)
    stmt = (
        update(Notification)
        .where(_ADMIN_INBOX, Notification.is_read.is_(False))
        .values(is_read=True, read_at=read_at)
        .returning(Notification.id)
    )
    if ids is not None:
        stmt = stmt.where(Notification.id.in_(ids))
    changed = list((await db.execute(stmt)).scalars())
    if changed:
        await log_admin_activity(
            db, ctx, action="update", resource_type="notification",
            resource_id=changed[0] if len(changed) == 1 else None,
            summary=(
                "Marked all notifications as read" if ids is None
                else f"Marked {len(changed)} notification(s) as read"
            ),
            metadata={"count": len(changed)},
        )
    return changed, read_at


async def delete_notifications(db: AsyncSession, ctx: AdminContext, ids: list[UUID]) -> list[UUID]:
    if not ids:
        return []
    deleted = list(
        (
            await db.execute(
                delete(Notification)
                .where(_ADMIN_INBOX, Notification.id.in_(ids))
                .returning(Notification.id)
            )
        ).scalars()
    )
    if deleted:
        await log_admin_activity(
            db, ctx, action="delete", resource_type="notification",
            resource_id=deleted[0] if len(deleted) == 1 else None,
            summary=f"Deleted {len(deleted)} notification(s)",
            metadata={"ids": [str(i) for i in deleted]},
        )
    return deleted


# --- Services (admin create / edit / archive) -------------------------------------------

_SERVICE_REQUIRED = frozenset(
    {
        "service_name", "category_id", "category_model", "sub_category_id", "sub_category_model",
        "type", "service_location_mode", "price", "pre_payment", "status", "service_image",
        "allows_custom_offer", "pricing_type", "approved", "feature", "feature_requested_status",
    }
)


def _normalize_service_fields(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("pricing_type"):
        data["pricing_type"] = str(data["pricing_type"]).upper()
    return data


async def create_service(db: AsyncSession, ctx: AdminContext, data: dict[str, Any]) -> Service:
    await _require_exists(db, Provider, data["provider_id"], "Provider")
    await _require_exists(db, Category, data["category_id"], "Category")
    await _require_exists(db, SubCategory, data["sub_category_id"], "Sub-category")
    data = _normalize_service_fields({k: v for k, v in data.items() if v is not None})
    row = Service(
        id=uuid4(),
        created_at=datetime.now(UTC),
        category_model=data.pop("category_model", {}),
        sub_category_model=data.pop("sub_category_model", {}),
        type=data.pop("type", "fixed"),
        service_location_mode=data.pop("service_location_mode", "onsite"),
        pre_payment=data.pop("pre_payment", False),
        status=data.pop("status", True),
        active=data.pop("active", True),
        service_image=data.pop("service_image", []),
        allows_custom_offer=data.pop("allows_custom_offer", False),
        pricing_type=data.pop("pricing_type", "ONE_TIME"),
        approved=data.pop("approved", False),
        feature=data.pop("feature", False),
        feature_requested_status=data.pop("feature_requested_status", "none"),
        is_archived=False,
        **data,
    )
    db.add(row)
    await db.flush()
    await log_admin_activity(
        db, ctx, action="create", resource_type="service", resource_id=row.id,
        summary=f"Created service {row.service_name}",
        metadata={"provider_id": str(row.provider_id), "approved": row.approved},
    )
    await db.refresh(row)
    return row


async def update_service(db: AsyncSession, ctx: AdminContext, row: Service, patch: dict[str, Any]) -> Service:
    if patch.get("category_id") is not None:
        await _require_exists(db, Category, patch["category_id"], "Category")
    if patch.get("sub_category_id") is not None:
        await _require_exists(db, SubCategory, patch["sub_category_id"], "Sub-category")
    changes = apply_patch(row, _normalize_service_fields(patch), non_nullable=_SERVICE_REQUIRED)
    if changes:
        await db.flush()
        await log_admin_activity(
            db, ctx, action="update", resource_type="service", resource_id=row.id,
            summary=f"Updated service {row.service_name}", metadata={"changes": changes},
        )
        await db.refresh(row)
    return row


async def archive_service(db: AsyncSession, ctx: AdminContext, row: Service) -> Service:
    """Soft delete, matching lolelink-admin `deleteServiceSlice` (bookings keep their FK)."""
    changes = apply_patch(
        row, {"is_archived": True, "status": False, "active": False}, non_nullable=frozenset()
    )
    if changes:
        await db.flush()
        await log_admin_activity(
            db, ctx, action="delete", resource_type="service", resource_id=row.id,
            summary=f"Archived service {row.service_name}", metadata={"changes": changes, "soft_delete": True},
        )
        await db.refresh(row)
    return row
