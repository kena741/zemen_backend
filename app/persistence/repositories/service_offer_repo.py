"""Repository for ServiceOffer persistence, queries, and booking linkage."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update

from app.domain.offer import ServiceOfferDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.booking import ServiceOffer
from app.persistence.sqlalchemy.models.catalog import Service
from app.persistence.sqlalchemy.models.identity import Customer, Provider


class ServiceOfferRepository(BaseRepository[ServiceOffer, ServiceOfferDomain]):
    model = ServiceOffer

    def to_domain(
        self,
        entity: ServiceOffer,
        service_name: str | None = None,
        customer_name: str | None = None,
        provider_name: str | None = None,
    ) -> ServiceOfferDomain:
        return ServiceOfferDomain(
            id=entity.id,
            service_id=entity.service_id,
            customer_id=entity.customer_id,
            provider_id=entity.provider_id,
            offered_price=float(entity.offered_price),
            status=entity.status,
            message=entity.message,
            booking_id=entity.booking_id,
            expires_at=entity.expires_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            booking_date=entity.booking_date,
            booking_address=entity.booking_address,
            service_description=entity.service_description,
            service_name=service_name,
            customer_name=customer_name,
            provider_name=provider_name,
        )

    async def create_offer(self, data: dict[str, Any]) -> ServiceOfferDomain:
        offer_id = data.get("id") or uuid4()
        now = datetime.now(timezone.utc)
        entity = ServiceOffer(
            id=offer_id,
            service_id=str(data["service_id"]),
            customer_id=str(data["customer_id"]),
            provider_id=str(data["provider_id"]),
            offered_price=Decimal(str(data["offered_price"])),
            message=data.get("message"),
            status=data.get("status", "pending"),
            booking_id=data.get("booking_id"),
            expires_at=data.get("expires_at"),
            created_at=data.get("created_at") or now,
            updated_at=data.get("updated_at") or now,
            booking_date=data.get("booking_date"),
            booking_address=data.get("booking_address"),
            service_description=data.get("service_description"),
        )
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return self.to_domain(entity)

    async def get_by_id_enriched(self, offer_id: UUID) -> ServiceOfferDomain | None:
        stmt = select(ServiceOffer).where(ServiceOffer.id == offer_id)
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()
        if not entity:
            return None
        return self.to_domain(entity)

    async def get_by_booking_id(self, booking_id: str) -> ServiceOfferDomain | None:
        stmt = (
            select(ServiceOffer)
            .where(ServiceOffer.booking_id == str(booking_id))
            .order_by(ServiceOffer.created_at.asc())
            .limit(1)
        )
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()
        return self.to_domain(entity) if entity else None

    async def has_pending_offer(self, service_id: str, customer_id: str, provider_id: str) -> bool:
        stmt = select(func.count(ServiceOffer.id)).where(
            ServiceOffer.service_id == service_id,
            ServiceOffer.customer_id == customer_id,
            ServiceOffer.provider_id == provider_id,
            ServiceOffer.status == "pending",
        )
        res = await self.session.execute(stmt)
        cnt = res.scalar_one() or 0
        return cnt > 0

    async def list_for_customer(
        self, customer_id: str, limit: int = 50, offset: int = 0
    ) -> list[ServiceOfferDomain]:
        stmt = (
            select(ServiceOffer)
            .where(ServiceOffer.customer_id == str(customer_id))
            .order_by(ServiceOffer.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return [self.to_domain(o) for o in res.scalars().all()]

    async def list_for_provider(
        self, provider_id: str, limit: int = 50, offset: int = 0
    ) -> list[ServiceOfferDomain]:
        stmt = (
            select(ServiceOffer)
            .where(ServiceOffer.provider_id == str(provider_id))
            .order_by(ServiceOffer.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return [self.to_domain(o) for o in res.scalars().all()]

    async def update_status(self, offer_id: UUID, status: str) -> ServiceOfferDomain | None:
        now = datetime.now(timezone.utc)
        stmt = (
            update(ServiceOffer)
            .where(ServiceOffer.id == offer_id)
            .values(status=status, updated_at=now)
            .returning(ServiceOffer)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        entity = res.scalar_one_or_none()
        return self.to_domain(entity) if entity else None

    async def attach_booking(self, offer_id: UUID, booking_id: str) -> ServiceOfferDomain | None:
        now = datetime.now(timezone.utc)
        stmt = (
            update(ServiceOffer)
            .where(ServiceOffer.id == offer_id)
            .values(booking_id=str(booking_id), updated_at=now)
            .returning(ServiceOffer)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        entity = res.scalar_one_or_none()
        return self.to_domain(entity) if entity else None

