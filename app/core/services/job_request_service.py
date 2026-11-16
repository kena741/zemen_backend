"""Service for Customer Job Requests and Provider Bidding."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.domain.crm import JobRequestDomain
from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.persistence.repositories.customer_repo import CustomerRepository
from app.persistence.repositories.job_request_repo import JobRequestRepository


class JobRequestService:
    def __init__(
        self,
        job_repo: JobRequestRepository,
        customer_repo: CustomerRepository,
    ) -> None:
        self.job_repo = job_repo
        self.customer_repo = customer_repo

    async def create_or_update_job(
        self,
        payload: dict[str, Any],
        actor_user_id: UUID,
        actor_role: str,
        customer_id: UUID | None = None,
    ) -> JobRequestDomain:
        data = dict(payload)
        if not data.get("id"):
            data["id"] = str(uuid4())

        if actor_role == "customer" or customer_id:
            c_id = customer_id
            if not c_id:
                cust = await self.customer_repo.get_by_user_id(actor_user_id)
                if cust:
                    c_id = cust.id
            if c_id:
                data["customer_id"] = str(c_id)

        if not data.get("title") and not data.get("description"):
            raise ValidationError("Job request must include a title or description.")

        return await self.job_repo.upsert_job_request(data)

    async def get_job(self, job_id: str) -> JobRequestDomain:
        job = await self.job_repo.get_by_id_enriched(job_id)
        if not job:
            raise EntityNotFoundError("JobRequest", job_id)
        return job

    async def list_customer_jobs(
        self, customer_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[JobRequestDomain]:
        return await self.job_repo.list_for_customer(customer_id, limit=limit, offset=offset)

    async def list_open_jobs(self, limit: int = 50, offset: int = 0) -> list[JobRequestDomain]:
        return await self.job_repo.list_open_jobs(limit=limit, offset=offset)

    async def list_provider_bids(self, provider_id: UUID) -> list[JobRequestDomain]:
        return await self.job_repo.list_provider_bids(provider_id)

    async def submit_bid(
        self,
        job_id: str,
        provider_id: UUID,
        bid_data: dict[str, Any],
    ) -> JobRequestDomain:
        job = await self.job_repo.get_by_id(job_id)
        if not job:
            raise EntityNotFoundError("JobRequest", job_id)

        now = datetime.now(timezone.utc)
        bid = {
            "providerId": str(provider_id),
            "bidPrice": str(bid_data.get("bid_price") or bid_data.get("bidPrice") or "0"),
            "message": bid_data.get("message"),
            "createdAt": now.isoformat(),
        }
        updated = await self.job_repo.add_bid(job_id, bid)
        if not updated:
            raise EntityNotFoundError("JobRequest", job_id)
        return updated

    async def mark_as_paid(self, job_id: str) -> bool:
        marked = await self.job_repo.mark_as_paid(job_id)
        if not marked:
            raise EntityNotFoundError("JobRequest", job_id)
        return True

    async def delete_job(self, job_id: str, customer_id: UUID) -> bool:
        deleted = await self.job_repo.delete_job_by_customer(job_id, customer_id)
        if not deleted:
            raise EntityNotFoundError("JobRequest", job_id)
        return True

