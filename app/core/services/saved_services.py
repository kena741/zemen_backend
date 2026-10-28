"""Customer-saved service drafts (`customers_service` + `customer_service_details`)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import CustomerServiceDetail, CustomersService


async def _parent(db: AsyncSession, customer_id: UUID) -> CustomersService | None:
    return (
        await db.execute(
            select(CustomersService)
            .where(CustomersService.customer_id == customer_id)
            .order_by(CustomersService.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _ensure_parent(db: AsyncSession, customer_id: UUID) -> CustomersService:
    row = await _parent(db, customer_id)
    if row is not None:
        return row
    row = CustomersService(id=uuid4(), customer_id=customer_id, created_at=datetime.now(UTC))
    db.add(row)
    await db.flush()
    return row


def _detail_payload(item: dict[str, Any], parent_id: UUID) -> dict[str, Any]:
    category = item.get("category_model") if isinstance(item.get("category_model"), dict) else {}
    return {
        "id": item.get("id") or uuid4(),
        "customer_service_id": parent_id,
        "service_name": item.get("service_name"),
        "description": item.get("description"),
        "price": float(item["price"]) if item.get("price") is not None else None,
        "service_images": item.get("service_image") or item.get("service_images") or [],
        "category_id": item.get("category_id") or category.get("id"),
        "category_name": category.get("categoryName") or category.get("category_name"),
        "category_image": category.get("image"),
        "category_active": category.get("active"),
        "category_model_id": item.get("category_id") or category.get("id"),
        "sub_category_id": item.get("sub_category_id"),
        "sub_category_model": item.get("sub_category_model"),
        "created_at": datetime.now(UTC),
    }


async def list_for_customer(db: AsyncSession, customer_id: UUID) -> list[CustomerServiceDetail]:
    parent = await _parent(db, customer_id)
    if parent is None:
        return []
    stmt = (
        select(CustomerServiceDetail)
        .where(CustomerServiceDetail.customer_service_id == parent.id)
        .order_by(CustomerServiceDetail.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def replace_for_customer(
    db: AsyncSession, customer_id: UUID, items: list[dict[str, Any]]
) -> list[CustomerServiceDetail]:
    parent = await _ensure_parent(db, customer_id)
    existing = {
        row.id: row
        for row in (
            await db.execute(
                select(CustomerServiceDetail).where(CustomerServiceDetail.customer_service_id == parent.id)
            )
        ).scalars()
    }
    out: list[CustomerServiceDetail] = []
    keep: set[UUID] = set()
    for item in items:
        payload = _detail_payload(item, parent.id)
        rid = payload["id"]
        if isinstance(rid, str):
            rid = UUID(rid)
            payload["id"] = rid
        row = existing.get(rid)
        if row is None:
            row = CustomerServiceDetail(**payload)
            db.add(row)
        else:
            for key, value in payload.items():
                if key != "id":
                    setattr(row, key, value)
        keep.add(row.id)
        out.append(row)
    for rid, row in existing.items():
        if rid not in keep:
            await db.delete(row)
    await db.flush()
    return out


async def delete_owned_detail(db: AsyncSession, customer_id: UUID, detail_id: UUID) -> bool:
    parent = await _parent(db, customer_id)
    if parent is None:
        return False
    row = (
        await db.execute(
            select(CustomerServiceDetail).where(
                CustomerServiceDetail.id == detail_id,
                CustomerServiceDetail.customer_service_id == parent.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    await db.delete(row)
    await db.flush()
    return True
