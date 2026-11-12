"""Repository for Customer Job Requests."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update

from app.domain.crm import JobRequestDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.booking import JobRequest
from app.persistence.sqlalchemy.models.identity import Customer


class JobRequestRepository(BaseRepository[JobRequest, JobRequestDomain]):
    model = JobRequest

    def to_domain(
        self,
        entity: JobRequest,
        customer_display_name: str | None = None,
        customer_display_phone: str | None = None,
    ) -> JobRequestDomain:
        return JobRequestDomain(
            id=entity.id,
            created_at=entity.created_at,
            title=entity.title,
            description=entity.description,
            price=entity.price,
            status=entity.status,
            accepted=entity.accepted,
            is_paid=entity.is_paid,
            customer_id=entity.customer_id,
            provider_id=entity.provider_id,
            customer_display_name=customer_display_name,
            customer_display_phone=customer_display_phone,
        )

    async def list_all_enriched(self) -> list[JobRequestDomain]:
        stmt = (
            select(
                JobRequest,
                Customer.first_name,
                Customer.last_name,
                Customer.phone,
            )
            .outerjoin(Customer, JobRequest.customer_id == Customer.id)
            .order_by(JobRequest.created_at.desc())
        )
        res = await self.session.execute(stmt)
        items: list[JobRequestDomain] = []
        for jr, c_first, c_last, c_phone in res.all():
            name = f"{c_first or ''} {c_last or ''}".strip() or "Customer"
            items.append(
                self.to_domain(
                    jr,
                    customer_display_name=name,
                    customer_display_phone=c_phone,
                )
            )
        return items

    async def update_job_request(
        self,
        job_id: str,
        action: str | None = None,
        title: str | None = None,
        description: str | None = None,
        price: str | None = None,
    ) -> JobRequest | None:
        values: dict[str, Any] = {}
        if action:
            if action == "accept":
                values["accepted"] = True
                values["status"] = "accepted"
            elif action == "reject":
                values["accepted"] = False
                values["status"] = "rejected"
            elif action == "pending":
                values["accepted"] = False
                values["status"] = "pending"

        if title is not None:
            values["title"] = title
        if description is not None:
            values["description"] = description
        if price is not None:
            values["price"] = price

        if not values:
            return await self.get_by_id(job_id)

        stmt = (
            update(self.model)
            .where(self.model.id == job_id)
            .values(**values)
            .returning(self.model)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def delete_by_id(self, job_id: str) -> int:
        stmt = delete(self.model).where(self.model.id == job_id)
        res = await self.session.execute(stmt)
        return int(res.rowcount or 0)

    async def delete_all_for_customer(self, customer_id: UUID) -> int:
        stmt = delete(self.model).where(self.model.customer_id == customer_id)
        res = await self.session.execute(stmt)
        return int(res.rowcount or 0)

    async def count_pending_badge(self) -> int:
        stmt = select(func.count(self.model.id)).where(
            (self.model.accepted.is_(False) | self.model.accepted.is_(None))
            & (self.model.status.in_(["pending", "none", None]))
        )
        res = await self.session.execute(stmt)
        return int(res.scalar_one() or 0)
