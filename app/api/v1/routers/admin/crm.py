"""Admin CRM and Customer Job Requests API router."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.admin.requests.crm import (
    DeleteJobRequestPayload,
    UpdateJobRequestPayload,
)
from app.api.v1.schemas.admin.responses.crm import (
    DeleteJobRequestResponse,
    JobRequestListResponse,
    JobRequestResponseItem,
)
from app.core.security.admin_deps import AdminContext, require_admin_permission
from app.core.services.admin.audit_service import AdminAuditService
from app.core.services.admin.crm_service import JobRequestAdminService
from app.persistence.repositories.activity_log_repo import ActivityLogRepository
from app.persistence.repositories.job_request_repo import JobRequestRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/admin", tags=["admin-crm"])

Db = Annotated[AsyncSession, Depends(get_db)]
CanReadCustomers = Annotated[AdminContext, Depends(require_admin_permission("customers:read"))]
CanWriteCustomers = Annotated[AdminContext, Depends(require_admin_permission("customers:write"))]


def _get_crm_service(db: AsyncSession) -> JobRequestAdminService:
    job_repo = JobRequestRepository(db)
    audit_repo = ActivityLogRepository(db)
    audit_service = AdminAuditService(audit_repo)

    return JobRequestAdminService(
        job_repo=job_repo,
        audit_service=audit_service,
    )


@router.get(
    "/job-requests",
    response_model=JobRequestListResponse,
    operation_id="admin_crm_list_job_requests",
    summary="List all customer job requests enriched with customer details",
)
@router.get(
    "/crm/job-requests",
    response_model=JobRequestListResponse,
    include_in_schema=False,
)
async def list_job_requests(_: CanReadCustomers, db: Db) -> JobRequestListResponse:
    service = _get_crm_service(db)
    items = await service.list_job_requests()
    return JobRequestListResponse(data=[JobRequestResponseItem.model_validate(i) for i in items])


@router.get(
    "/job-requests/badge-count",
    operation_id="admin_crm_job_requests_badge_count",
    summary="Count pending customer job requests for sidebar badge",
)
async def get_job_requests_badge_count(_: CanReadCustomers, db: Db) -> dict[str, int]:
    service = _get_crm_service(db)
    count = await service.count_pending_badge()
    return {"count": count}


@router.patch(
    "/job-requests",
    operation_id="admin_crm_update_job_request",
    summary="Update customer job request status, action, or details",
)
async def update_job_request(
    body: UpdateJobRequestPayload,
    ctx: CanWriteCustomers,
    db: Db,
) -> dict[str, bool]:
    if not body.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="id is required in payload",
        )
    service = _get_crm_service(db)
    await service.update_job_request(
        job_id=body.id,
        action=body.action,
        title=body.title,
        description=body.description,
        price=body.price,
        ctx=ctx,
    )
    return {"ok": True}


@router.delete(
    "/job-requests",
    response_model=DeleteJobRequestResponse,
    operation_id="admin_crm_delete_job_requests",
    summary="Delete single job request or all job requests for a customer",
)
async def delete_job_requests(
    body: DeleteJobRequestPayload,
    ctx: CanWriteCustomers,
    db: Db,
) -> DeleteJobRequestResponse:
    service = _get_crm_service(db)
    count = await service.delete_job_requests(
        job_id=body.id,
        customer_id=body.customer_id,
        ctx=ctx,
    )
    return DeleteJobRequestResponse(ok=True, deleted=count)
