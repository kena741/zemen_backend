"""Provider-owned service management, tier limit checks, and CRUD."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.catalog import ServiceDomain
from app.domain.exceptions import EntityNotFoundError, ValidationError
from app.persistence.repositories.provider_repo import ProviderRepository
from app.persistence.repositories.service_repo import ServiceRepository
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


class ProviderServiceManagementService:
    def __init__(
        self,
        service_repo: ServiceRepository,
        provider_repo: ProviderRepository,
    ) -> None:
        self.service_repo = service_repo
        self.provider_repo = provider_repo

    async def list_provider_services(
        self,
        provider_id: UUID,
        include_archived: bool = False,
    ) -> list[ServiceDomain]:
        return await self.service_repo.list_services(
            include_archived=include_archived,
            provider_id=provider_id,
        )

    async def get_service(self, provider_id: UUID, service_id: UUID) -> ServiceDomain:
        service = await self.service_repo.get_by_id_enriched(service_id)
        if not service or service.provider_id != provider_id:
            raise EntityNotFoundError("Service", service_id)
        return service

    async def create_service(self, provider_id: UUID, data: dict[str, Any]) -> ServiceDomain:
        # 1. Check provider tier limit
        provider = await self.provider_repo.get_by_id(provider_id)
        if provider and provider.service_tier_max > 0:
            active_count = await self.service_repo.count_active_by_provider(provider_id)
            if active_count >= provider.service_tier_max:
                raise ValidationError(
                    f"Tier limit reached ({active_count}/{provider.service_tier_max} services). Please upgrade your tier."
                )

        now = datetime.now(timezone.utc)
        domain = ServiceDomain(
            id=uuid4(),
            provider_id=provider_id,
            service_name=data["service_name"],
            description=data.get("description"),
            address=data.get("address"),
            category_id=data["category_id"],
            category_name=data.get("category_name"),
            sub_category_id=data["sub_category_id"],
            sub_category_name=data.get("sub_category_name"),
            type=data.get("type", "fixed"),
            service_location_mode=data.get("service_location_mode", "on_site"),
            price=float(data["price"]),
            discount=data.get("discount"),
            pre_payment=bool(data.get("pre_payment", False)),
            feature=False,
            status=bool(data.get("status", True)),
            active=data.get("active", True),
            slug=data.get("slug"),
            service_image=list(data.get("service_image") or []),
            video=data.get("video"),
            duration=data.get("duration"),
            is_archived=False,
            approved=False,
            feature_requested_status="none",
            created_at=now,
        )
        return await self.service_repo.create_service(domain)

    async def update_service(
        self,
        provider_id: UUID,
        service_id: UUID,
        patch: dict[str, Any],
    ) -> ServiceDomain:
        updated = await self.service_repo.update_service_fields(
            service_id=service_id,
            provider_id=provider_id,
            patch=patch,
        )
        if not updated:
            raise EntityNotFoundError("Service", service_id)
        return updated

    async def delete_service(self, provider_id: UUID, service_id: UUID) -> bool:
        deleted = await self.service_repo.delete_service(service_id, provider_id)
        if not deleted:
            raise EntityNotFoundError("Service", service_id)
        return True

    async def request_featured(self, provider_id: UUID, service_id: UUID) -> ServiceDomain:
        service = await self.get_service(provider_id, service_id)
        await self.service_repo.update_feature_request(
            service_id=service_id,
            feature=False,
            feature_status="pending",
        )
        updated = await self.service_repo.get_by_id_enriched(service_id)
        return updated or service

    async def count_active_services(self, provider_id: UUID) -> int:
        return await self.service_repo.count_active_by_provider(provider_id)


# Backward compatibility helpers
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
    now = datetime.now(timezone.utc)
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
        feature=False,
        status=bool(data.get("status", True)),
        active=data.get("active", True),
        slug=data.get("slug"),
        service_image=list(data.get("service_image") or []),
        location=data.get("location"),
        duration=data.get("duration"),
        created_at=now,
        is_archived=False,
        approved=False,
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
    try:
        async with db.begin_nested():
            await db.delete(service)
            await db.flush()
        return None
    except IntegrityError:
        return (
            "Cannot delete this service because it is linked to bookings or other records."
        )
