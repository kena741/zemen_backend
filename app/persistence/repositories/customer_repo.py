"""Repository for Customer persistence and statistics."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update

from app.domain.customer import (
    CustomerDomain,
    CustomerJobRequestItemDomain,
    CustomerStatsDomain,
)
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.booking import BookedService, JobRequest
from app.persistence.sqlalchemy.models.identity import Customer
from app.persistence.sqlalchemy.models.provider_ops import ProviderCustomer


class CustomerRepository(BaseRepository[Customer, CustomerDomain]):
    model = Customer

    def to_domain(self, entity: Customer) -> CustomerDomain:
        amt = float(entity.wallet_amount) if entity.wallet_amount is not None else 0.0
        return CustomerDomain(
            id=entity.id,
            user_id=entity.user_id,
            first_name=entity.first_name,
            last_name=entity.last_name,
            phone=entity.phone,
            email=entity.email,
            country_code=entity.country_code,
            user_name=entity.user_name,
            profile_pic=entity.profile_pic,
            fcm_token=entity.fcm_token,
            login_type=entity.login_type,
            wallet_amount=amt,
            active=entity.active,
            slug=entity.slug,
            address=entity.address,
            default_address=entity.default_address,
            customer_addresses=entity.customer_addresses,
            signup_source=entity.signup_source,
            admin_note=entity.admin_note,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            archived_at=entity.archived_at,
        )

    async def list_customers(
        self,
        include_archived: bool = True,
        offset: int = 0,
        limit: int = 1000,
    ) -> list[CustomerDomain]:
        stmt = select(self.model)
        if not include_archived:
            stmt = stmt.where(self.model.archived_at.is_(None))
        stmt = stmt.order_by(self.model.created_at.desc()).offset(offset).limit(limit)
        res = await self.session.execute(stmt)
        return [self.to_domain(r) for r in res.scalars().all()]

    async def list_by_provider_id(self, provider_id: UUID) -> list[CustomerDomain]:
        stmt = (
            select(Customer)
            .join(ProviderCustomer, ProviderCustomer.customer_id == Customer.id)
            .where(ProviderCustomer.provider_id == provider_id)
            .order_by(ProviderCustomer.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return [self.to_domain(c) for c in res.scalars().all()]

    async def get_by_email(self, email: str) -> CustomerDomain | None:
        stmt = select(self.model).where(func.lower(self.model.email) == email.lower().strip())
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()
        return self.to_domain(entity) if entity else None

    async def get_by_phone(self, phone: str) -> CustomerDomain | None:
        clean = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
        stmt = select(self.model).where(self.model.phone == clean)
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()
        return self.to_domain(entity) if entity else None

    async def get_by_slug(self, slug: str) -> CustomerDomain | None:
        stmt = select(self.model).where(self.model.slug == slug.strip())
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()
        return self.to_domain(entity) if entity else None

    async def get_stats(self, customer_id: UUID) -> CustomerStatsDomain:
        stmt = (
            select(BookedService)
            .where(BookedService.customer_id == customer_id, BookedService.is_archived.is_(False))
            .order_by(BookedService.booking_date.desc())
        )
        res = await self.session.execute(stmt)
        bookings = res.scalars().all()

        completed = 0
        active = 0
        total_spend = 0.0
        last_date = bookings[0].booking_date if bookings else None

        for b in bookings:
            amt = float(b.total_amount or b.price or 0)
            if b.status == "completed" or b.payment_completed:
                completed += 1
                total_spend += amt
            elif b.status in ("pending", "accepted", "in_progress", "active"):
                active += 1

        return CustomerStatsDomain(
            completed_bookings=completed,
            active_bookings=active,
            total_spend=round(total_spend, 2),
            last_booking_date=last_date,
        )

    async def archive(self, customer_id: UUID, should_archive: bool) -> CustomerDomain | None:
        new_archived_at = datetime.now(timezone.utc) if should_archive else None
        stmt = (
            update(self.model)
            .where(self.model.id == customer_id)
            .values(archived_at=new_archived_at, updated_at=datetime.now(timezone.utc))
            .returning(self.model)
        )
        res = await self.session.execute(stmt)
        updated = res.scalar_one_or_none()
        return self.to_domain(updated) if updated else None

    async def update_note(self, customer_id: UUID, note: str | None) -> CustomerDomain | None:
        stmt = (
            update(self.model)
            .where(self.model.id == customer_id)
            .values(admin_note=note, updated_at=datetime.now(timezone.utc))
            .returning(self.model)
        )
        res = await self.session.execute(stmt)
        updated = res.scalar_one_or_none()
        return self.to_domain(updated) if updated else None

    async def list_job_requests(self, customer_id: UUID) -> list[CustomerJobRequestItemDomain]:
        stmt = (
            select(JobRequest)
            .where(JobRequest.customer_id == customer_id)
            .order_by(JobRequest.created_at.desc())
        )
        res = await self.session.execute(stmt)
        rows = res.scalars().all()
        return [
            CustomerJobRequestItemDomain(
                id=r.id,
                created_at=r.created_at,
                title=r.title,
                description=r.description,
                price=r.price,
                status=r.status,
                accepted=r.accepted,
                is_paid=r.is_paid,
            )
            for r in rows
        ]

    async def resolve_booker(self) -> CustomerDomain | None:
        stmt = (
            select(self.model)
            .where(self.model.active.is_(True), self.model.archived_at.is_(None))
            .order_by(self.model.created_at.asc())
            .limit(1)
        )
        res = await self.session.execute(stmt)
        first = res.scalar_one_or_none()
        return self.to_domain(first) if first else None
