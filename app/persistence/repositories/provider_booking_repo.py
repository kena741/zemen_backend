"""Repository for Provider service and hire history."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, update

from app.domain.provider import (
    ProviderBookingHistoryItemDomain,
    RepeatCustomerDomain,
    ServiceHistoryStatsDomain,
)
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.booking import BookedService
from app.persistence.sqlalchemy.models.identity import Customer


class ProviderBookingRepository(BaseRepository[BookedService, ProviderBookingHistoryItemDomain]):
    model = BookedService

    def to_domain(self, entity: BookedService) -> ProviderBookingHistoryItemDomain:
        cust_name = f"{entity.first_name} {entity.last_name}".strip()
        amt = float(entity.total_amount or entity.price or 0)
        is_past = bool(entity.description and entity.description.startswith("[Past hire]"))
        return ProviderBookingHistoryItemDomain(
            id=entity.id,
            service_name=entity.service_name,
            status=entity.status,
            payment_status=entity.payment_status,
            payment_completed=entity.payment_completed,
            amount=amt,
            created_at=entity.created_at,
            booking_date=entity.booking_date,
            customer_id=entity.customer_id,
            customer_name=cust_name or "Customer",
            is_past_hire=is_past,
            note=entity.description,
            follow_up=entity.admin_note,
        )

    async def list_for_provider(
        self, provider_id: UUID
    ) -> tuple[
        list[ProviderBookingHistoryItemDomain],
        ServiceHistoryStatsDomain,
        list[RepeatCustomerDomain],
    ]:
        stmt = (
            select(self.model)
            .where(
                self.model.provider_id == provider_id,
                self.model.is_archived.is_(False),
            )
            .order_by(self.model.created_at.desc())
        )
        res = await self.session.execute(stmt)
        entities = res.scalars().all()

        # Count occurrences per customer to determine prior completed count & repeat customers
        customer_counts: Counter[UUID] = Counter()
        customer_names: dict[UUID, str] = {}
        for e in entities:
            if e.customer_id:
                customer_counts[e.customer_id] += 1
                if e.customer_id not in customer_names:
                    customer_names[e.customer_id] = f"{e.first_name} {e.last_name}".strip() or "Customer"

        items: list[ProviderBookingHistoryItemDomain] = []
        total_completed = 0
        total_earnings = 0.0

        for e in entities:
            domain = self.to_domain(e)
            hire_cnt = customer_counts.get(e.customer_id, 0) if e.customer_id else 0
            domain.hired_before = hire_cnt > 1
            domain.prior_completed_count = max(0, hire_cnt - 1)
            if e.status == "completed" or e.payment_completed:
                total_completed += 1
                total_earnings += float(domain.amount)
            items.append(domain)

        total_bookings = len(entities)
        repeat_count = sum(1 for cnt in customer_counts.values() if cnt > 1)
        unique_customers = len(customer_counts)
        repeat_rate = (repeat_count / unique_customers * 100.0) if unique_customers > 0 else 0.0

        stats = ServiceHistoryStatsDomain(
            total_bookings=total_bookings,
            completed_bookings=total_completed,
            total_earnings=round(total_earnings, 2),
            repeat_customer_rate=round(repeat_rate, 1),
        )

        repeat_customers = [
            RepeatCustomerDomain(
                customer_id=cid,
                customer_name=customer_names.get(cid, "Customer"),
                hire_count=cnt,
            )
            for cid, cnt in customer_counts.items()
            if cnt > 1
        ]

        return items, stats, repeat_customers

    async def log_past_hire(
        self,
        provider_id: UUID,
        customer_id: UUID | None,
        service_id: UUID | None,
        booking_date: datetime,
        amount: float,
        note: str | None = None,
        admin_note: str | None = None,
    ) -> BookedService:
        now = datetime.now(timezone.utc)
        desc = f"[Past hire] {note}".strip() if note else "[Past hire] Logged by admin"

        first_name = "Walk-in"
        last_name = "Customer"
        phone = "+251900000000"
        email = None
        if customer_id:
            cust_res = await self.session.execute(
                select(Customer).where(Customer.id == customer_id)
            )
            cust = cust_res.scalar_one_or_none()
            if cust:
                first_name = cust.first_name or first_name
                last_name = cust.last_name or last_name
                phone = cust.phone_number or phone
                email = cust.email

        booking = BookedService(
            id=uuid4(),
            provider_id=provider_id,
            customer_id=customer_id,
            service_id=service_id,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone,
            email=email,
            price=Decimal(str(amount)),
            total_amount=Decimal(str(amount)),
            quantity=1,
            tax_list=[],
            booking_date=booking_date,
            payment_completed=True,
            payment_status="paid",
            status="completed",
            description=desc,
            admin_note=admin_note,
            created_at=now,
            is_archived=False,
        )
        self.session.add(booking)
        await self.session.flush()
        return booking

    async def update_hire_note(
        self,
        provider_id: UUID,
        booking_id: UUID,
        admin_note: str | None,
    ) -> BookedService | None:
        stmt = (
            update(self.model)
            .where(self.model.id == booking_id, self.model.provider_id == provider_id)
            .values(admin_note=admin_note)
            .returning(self.model)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()
