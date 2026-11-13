"""Core service for CRM and Customer Job Requests."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.core.security.admin_deps import AdminContext
from app.core.services.admin.audit_service import AdminAuditService
from app.domain.crm import JobRequestDomain
from app.persistence.repositories.job_request_repo import JobRequestRepository


class JobRequestAdminService:
    def __init__(
        self,
        job_repo: JobRequestRepository,
        audit_service: AdminAuditService,
    ) -> None:
        self.job_repo = job_repo
        self.audit_service = audit_service

    async def list_job_requests(self) -> list[JobRequestDomain]:
        return await self.job_repo.list_all_enriched()

    async def update_job_request(
        self,
        job_id: str,
        action: str | None = None,
        title: str | None = None,
        description: str | None = None,
        price: str | None = None,
        ctx: AdminContext | None = None,
    ) -> JobRequestDomain:
        updated = await self.job_repo.update_job_request(
            job_id=job_id,
            action=action,
            title=title,
            description=description,
            price=price,
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job request not found")

        action_name = f"job_request.{action}" if action else "job_request.update"
        await self.audit_service.log_action(
            action=action_name,
            resource_type="job_request",
            resource_id=job_id,
            summary=f"Admin updated job request {job_id} ({action or 'fields'})",
            metadata={"action": action, "title": title, "price": price},
            ctx=ctx,
        )
        return self.job_repo.to_domain(updated)

    async def delete_job_requests(
        self,
        job_id: str | None = None,
        customer_id: UUID | None = None,
        ctx: AdminContext | None = None,
    ) -> int:
        deleted_count = 0
        if job_id:
            deleted_count = await self.job_repo.delete_by_id(job_id)
            if deleted_count > 0:
                await self.audit_service.log_action(
                    action="job_request.delete",
                    resource_type="job_request",
                    resource_id=job_id,
                    summary=f"Deleted job request {job_id}",
                    ctx=ctx,
                )
        elif customer_id:
            deleted_count = await self.job_repo.delete_all_for_customer(customer_id)
            if deleted_count > 0:
                await self.audit_service.log_action(
                    action="job_request.delete_bulk",
                    resource_type="job_request",
                    resource_id=str(customer_id),
                    summary=f"Deleted all {deleted_count} job requests for customer {customer_id}",
                    ctx=ctx,
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Either id or customerId must be provided",
            )

        return deleted_count

    async def count_pending_badge(self) -> int:
        return await self.job_repo.count_pending_badge()

