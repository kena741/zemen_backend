"""Provider-owned service CRUD (table: service)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.persistence.sqlalchemy.models import Service

SERVICE_PATCH_FIELDS = frozenset(
    {
        "service_name",
        "description",
        "address",
        "category_id",
        "category_model",
        "sub_category_id",
        "sub_category_model",
        "type",
        "service_location_mode",
        "price",
        "discount",
        "pre_payment",
        "status",
        "active",
        "slug",
        "service_image",
        "location",
        "duration",
        "allows_custom_offer",
        "pricing_type",
        "billing_interval",
        "billing_interval_count",
        "pre_payment_percent",
        "is_archived",
    }
)


async def list_provider_services(
    db: AsyncSession,
    provider_id: UUID,
    *,
    include_archived: bool = False,
) -> list[Service]:
    stmt = select(Service).where(Service.provider_id == provider_id)
    if not include_archived:
        stmt = stmt.where(Service.is_archived.is_not(True))
    stmt = stmt.order_by(Service.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


async def get_owned_service(
    db: AsyncSession, provider_id: UUID, service_id: UUID
) -> Service | None:
    return (
        await db.execute(
            select(Service).where(
                Service.id == service_id,
                Service.provider_id == provider_id,
            )
        )
    ).scalar_one_or_none()


async def create_service(
    db: AsyncSession,
    *,
    provider_id: UUID,
    data: dict[str, Any],
) -> Service:
    now = datetime.now(UTC)
    service = Service(
        id=uuid4(),
        provider_id=provider_id,
        service_name=data["service_name"],
        description=data.get("description"),
        address=data.get("address"),
        category_id=data["category_id"],
        category_model=data.get("category_model") or {},
        sub_category_id=data["sub_category_id"],
        sub_category_model=data.get("sub_category_model") or {},
        type=data.get("type") or "fixed",
        service_location_mode=data.get("service_location_mode") or "onsite",
        price=Decimal(str(data["price"])),
        discount=data.get("discount"),
        pre_payment=bool(data.get("pre_payment", False)),
        feature=False,  # featured is a paid admin path — never set by client create
        status=bool(data.get("status", True)),
        active=data.get("active", True),
        slug=data.get("slug"),
        service_image=list(data.get("service_image") or []),
        location=data.get("location"),
        duration=data.get("duration"),
        created_at=now,
        is_archived=False,
        approved=False,  # admin approval required
        allows_custom_offer=bool(data.get("allows_custom_offer", False)),
        pricing_type=(data.get("pricing_type") or "ONE_TIME").upper(),
        billing_interval=data.get("billing_interval"),
        billing_interval_count=data.get("billing_interval_count"),
        pre_payment_percent=data.get("pre_payment_percent"),
    )
    db.add(service)
    await db.flush()
    await db.refresh(service)
    return service


async def update_service(
    db: AsyncSession, service: Service, patch: dict[str, Any]
) -> Service:
    cleaned = {k: v for k, v in patch.items() if k in SERVICE_PATCH_FIELDS and v is not None}
    if "price" in cleaned:
        cleaned["price"] = Decimal(str(cleaned["price"]))
    if "pricing_type" in cleaned:
        cleaned["pricing_type"] = str(cleaned["pricing_type"]).upper()
    for key, value in cleaned.items():
        setattr(service, key, value)
    await db.flush()
    await db.refresh(service)
    return service


async def delete_service(db: AsyncSession, service: Service) -> str | None:
    """Hard delete matching Flutter. Returns error message on FK conflict."""
    try:
        async with db.begin_nested():
            await db.delete(service)
            await db.flush()
        return None
    except IntegrityError:
        return (
            "Cannot delete this service because it is linked to bookings or other records."
        )
