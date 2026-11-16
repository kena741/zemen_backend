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
            bid_list=entity.bid_list or [],
            bid_price=entity.bid_price,
            handyman_id=entity.handyman_id,
            service_id=entity.service_id,
            service_model_list=entity.service_model_list or [],
        )

    async def get_by_id_enriched(self, job_id: str) -> JobRequestDomain | None:
        stmt = (
            select(
                JobRequest,
                Customer.first_name,
                Customer.last_name,
                Customer.phone,
            )
            .outerjoin(Customer, JobRequest.customer_id == Customer.id)
            .where(JobRequest.id == job_id)
        )
        res = await self.session.execute(stmt)
        row = res.first()
        if not row:
            return None
        jr, c_first, c_last, c_phone = row
        name = f"{c_first or ''} {c_last or ''}".strip() or "Customer"
        return self.to_domain(
            jr,
            customer_display_name=name,
            customer_display_phone=c_phone,
        )

    async def upsert_job_request(self, payload: dict[str, Any]) -> JobRequestDomain:
        job_id = str(payload.get("id") or "")
        stmt = select(JobRequest).where(JobRequest.id == job_id)
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()

        def _to_uuid(val: Any) -> UUID | None:
            if not val:
                return None
            return val if isinstance(val, UUID) else UUID(str(val))

        def _to_dt(val: Any) -> datetime | None:
            if not val:
                return None
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            return None

        if entity is None:
            now = datetime.now(timezone.utc)
            entity = JobRequest(
                id=job_id,
                created_at=_to_dt(payload.get("created_at") or payload.get("createdAt")) or now,
                title=payload.get("title"),
                description=payload.get("description"),
                price=str(payload.get("price")) if payload.get("price") is not None else None,
                status=payload.get("status", "accepted"),
                accepted=bool(payload.get("accepted", False)),
                is_paid=bool(payload.get("is_paid", False)),
                bid_list=payload.get("bid_list") or payload.get("bidList") or [],
                bid_price=str(payload.get("bid_price") or payload.get("bidPrice") or "0"),
                customer_id=_to_uuid(payload.get("customer_id") or payload.get("customerId")),
                provider_id=_to_uuid(payload.get("provider_id") or payload.get("providerId")),
                handyman_id=str(payload.get("handyman_id") or payload.get("handymanId") or ""),
                service_id=_to_uuid(payload.get("service_id") or payload.get("serviceId")),
                service_model_list=payload.get("service_model_list") or payload.get("serviceModelList") or [],
            )
            self.session.add(entity)
        else:
            for k, v in payload.items():
                if k == "id":
                    continue
                norm_k = {
                    "createdAt": "created_at",
                    "customerId": "customer_id",
                    "providerId": "provider_id",
                    "handymanId": "handyman_id",
                    "serviceId": "service_id",
                    "bidList": "bid_list",
                    "bidPrice": "bid_price",
                    "serviceModelList": "service_model_list",
                }.get(k, k)

                if hasattr(entity, norm_k):
                    if norm_k in {"customer_id", "provider_id", "service_id"}:
                        setattr(entity, norm_k, _to_uuid(v))
                    elif norm_k in {"created_at"}:
                        setattr(entity, norm_k, _to_dt(v))
                    else:
                        setattr(entity, norm_k, v)

        await self.session.commit()
        await self.session.refresh(entity)
        return self.to_domain(entity)

    async def list_for_customer(
        self, customer_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[JobRequestDomain]:
        stmt = (
            select(JobRequest)
            .where(JobRequest.customer_id == customer_id)
            .order_by(JobRequest.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return [self.to_domain(jr) for jr in res.scalars().all()]

    async def list_open_jobs(self, limit: int = 50, offset: int = 0) -> list[JobRequestDomain]:
        stmt = (
            select(
                JobRequest,
                Customer.first_name,
                Customer.last_name,
                Customer.phone,
            )
            .outerjoin(Customer, JobRequest.customer_id == Customer.id)
            .where(
                (JobRequest.accepted.is_(False) | JobRequest.accepted.is_(None))
            )
            .order_by(JobRequest.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        items: list[JobRequestDomain] = []
        for jr, c_first, c_last, c_phone in res.all():
            name = f"{c_first or ''} {c_last or ''}".strip() or "Customer"
            items.append(self.to_domain(jr, customer_display_name=name, customer_display_phone=c_phone))
        return items

    async def list_provider_bids(self, provider_id: UUID) -> list[JobRequestDomain]:
        stmt = select(JobRequest).order_by(JobRequest.created_at.desc()).limit(200)
        res = await self.session.execute(stmt)
        matching: list[JobRequestDomain] = []
        p_str = str(provider_id)
        for jr in res.scalars().all():
            bids = jr.bid_list or []
            if any(isinstance(b, dict) and str(b.get("providerId") or b.get("provider_id")) == p_str for b in bids):
                matching.append(self.to_domain(jr))
        return matching

    async def add_bid(self, job_id: str, bid: dict[str, Any]) -> JobRequestDomain | None:
        stmt = select(JobRequest).where(JobRequest.id == job_id)
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()
        if not entity:
            return None

        current_bids = list(entity.bid_list or [])
        # Replace if existing bid from same provider, or append
        p_str = str(bid.get("providerId") or bid.get("provider_id"))
        replaced = False
        for i, b in enumerate(current_bids):
            if isinstance(b, dict) and str(b.get("providerId") or b.get("provider_id")) == p_str:
                current_bids[i] = bid
                replaced = True
                break
        if not replaced:
            current_bids.append(bid)

        entity.bid_list = current_bids
        await self.session.commit()
        await self.session.refresh(entity)
        return self.to_domain(entity)

    async def mark_as_paid(self, job_id: str) -> bool:
        stmt = update(JobRequest).where(JobRequest.id == job_id).values(is_paid=True)
        res = await self.session.execute(stmt)
        await self.session.commit()
        return bool(res.rowcount and res.rowcount > 0)

    async def delete_job_by_customer(self, job_id: str, customer_id: UUID) -> bool:
        stmt = delete(JobRequest).where(
            JobRequest.id == job_id,
            JobRequest.customer_id == customer_id,
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return bool(res.rowcount and res.rowcount > 0)

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

