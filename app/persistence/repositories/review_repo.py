"""Repository for Customer Reviews and ratings aggregation."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.review import ReviewCustomerDomain
from app.persistence.sqlalchemy.models.catalog import Service
from app.persistence.sqlalchemy.models.identity import Customer
from app.persistence.sqlalchemy.models.social import ReviewCustomer


class ReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def to_domain(
        self,
        entity: ReviewCustomer,
        customer_name: str | None = None,
        customer_image: str | None = None,
    ) -> ReviewCustomerDomain:
        r_float = 0.0
        if entity.rating:
            try:
                r_float = float(entity.rating)
            except (ValueError, TypeError):
                r_float = 0.0

        return ReviewCustomerDomain(
            id=entity.id,
            comment=entity.comment,
            rating=r_float,
            customer_id=entity.customer_id,
            service_id=entity.service_id,
            booking_id=entity.booking_id,
            date=entity.date or datetime.now(timezone.utc),
            customer_name=customer_name,
            customer_image=customer_image,
        )

    async def add_review(self, data: dict[str, Any]) -> ReviewCustomerDomain:
        now = datetime.now(timezone.utc)
        r_val = float(data.get("rating") or 5.0)
        review_id = data.get("id") or uuid4()

        entity = ReviewCustomer(
            id=review_id,
            comment=data.get("comment", ""),
            rating=str(r_val),
            customer_id=data.get("customer_id"),
            service_id=data.get("service_id"),
            booking_id=data.get("booking_id"),
            date=data.get("date") or now,
        )
        self.session.add(entity)

        # Update service review aggregates if service_id provided
        if data.get("service_id"):
            s_stmt = select(Service).where(Service.id == data["service_id"])
            s_res = await self.session.execute(s_stmt)
            service = s_res.scalar_one_or_none()
            if service:
                curr_sum = float(service.review_sum or 0.0)
                curr_cnt = int(service.review_count or 0)
                service.review_sum = Decimal(str(curr_sum + r_val))
                service.review_count = curr_cnt + 1

        await self.session.commit()
        await self.session.refresh(entity)
        return self.to_domain(entity)

    async def list_for_service(
        self, service_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[ReviewCustomerDomain]:
        stmt = (
            select(
                ReviewCustomer,
                func.concat(Customer.first_name, " ", Customer.last_name).label("c_name"),
                Customer.profile_pic.label("c_img"),
            )
            .outerjoin(Customer, ReviewCustomer.customer_id == Customer.id)
            .where(ReviewCustomer.service_id == service_id)
            .order_by(ReviewCustomer.date.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        items: list[ReviewCustomerDomain] = []
        for rc, name, img in res.all():
            items.append(
                self.to_domain(
                    rc,
                    customer_name=name.strip() if name else "Customer",
                    customer_image=img,
                )
            )
        return items

    async def get_by_booking_id(self, booking_id: UUID) -> ReviewCustomerDomain | None:
        stmt = (
            select(
                ReviewCustomer,
                func.concat(Customer.first_name, " ", Customer.last_name).label("c_name"),
                Customer.profile_pic.label("c_img"),
            )
            .outerjoin(Customer, ReviewCustomer.customer_id == Customer.id)
            .where(ReviewCustomer.booking_id == booking_id)
        )
        res = await self.session.execute(stmt)
        row = res.first()
        if not row:
            return None
        rc, name, img = row
        return self.to_domain(
            rc,
            customer_name=name.strip() if name else "Customer",
            customer_image=img,
        )

