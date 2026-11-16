"""Router for Custom Job Requests and Provider Bidding."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.job import JobBidBody, JobCreate, JobPatch, JobRequestOut
from app.core.security.deps import RequireAuth, RequireCustomer, RequireProvider
from app.core.services.job_request_service import JobRequestService
from app.persistence.repositories.customer_repo import CustomerRepository
from app.persistence.repositories.job_request_repo import JobRequestRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def get_job_request_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JobRequestService:
    return JobRequestService(
        job_repo=JobRequestRepository(db),
        customer_repo=CustomerRepository(db),
    )


@router.get(
    "",
    response_model=Page[JobRequestOut],
    summary="List job requests for customer or provider profile",
)
async def list_mine(
    ctx: RequireAuth,
    service: Annotated[JobRequestService, Depends(get_job_request_service)],
    as_role: Literal["customer", "provider"] = Query("customer", alias="as"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[JobRequestOut]:
    if as_role == "customer":
        assert ctx.customer_id is not None
        rows = await service.list_customer_jobs(ctx.customer_id, limit=limit, offset=offset)
    else:
        assert ctx.provider_id is not None
        rows = await service.list_provider_bids(ctx.provider_id)
    return Page(
        items=[JobRequestOut.model_validate(r) for r in rows],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.get(
    "/open",
    response_model=Page[JobRequestOut],
    summary="List open job requests available for providers to bid on",
)
async def list_open_jobs(
    service: Annotated[JobRequestService, Depends(get_job_request_service)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[JobRequestOut]:
    rows = await service.list_open_jobs(limit=limit, offset=offset)
    return Page(
        items=[JobRequestOut.model_validate(r) for r in rows],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.get(
    "/my-bids",
    response_model=list[JobRequestOut],
    summary="List job requests containing bids from the authenticated provider",
)
async def list_my_bids(
    ctx: RequireProvider,
    service: Annotated[JobRequestService, Depends(get_job_request_service)],
) -> list[JobRequestOut]:
    assert ctx.provider_id is not None
    rows = await service.list_provider_bids(ctx.provider_id)
    return [JobRequestOut.model_validate(r) for r in rows]


@router.post(
    "",
    response_model=JobRequestOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create or upsert a customer job listing (addJobRequest contract)",
)
async def create_job(
    body: JobCreate,
    ctx: RequireCustomer,
    service: Annotated[JobRequestService, Depends(get_job_request_service)],
) -> JobRequestOut:
    created = await service.create_or_update_job(
        payload=body.model_dump(exclude_unset=True),
        actor_user_id=ctx.user_id,
        actor_role="customer",
        customer_id=ctx.customer_id,
    )
    return JobRequestOut.model_validate(created)


@router.get(
    "/{job_id}",
    response_model=JobRequestOut,
    summary="Get single job request detail by ID",
)
async def get_job(
    job_id: str,
    service: Annotated[JobRequestService, Depends(get_job_request_service)],
) -> JobRequestOut:
    item = await service.get_job(job_id)
    return JobRequestOut.model_validate(item)


@router.patch(
    "/{job_id}",
    response_model=JobRequestOut,
    summary="Customer patch of listing fields",
)
async def patch_job(
    job_id: str,
    body: JobPatch,
    ctx: RequireCustomer,
    service: Annotated[JobRequestService, Depends(get_job_request_service)],
) -> JobRequestOut:
    patch_data = body.model_dump(exclude_unset=True)
    patch_data["id"] = job_id
    updated = await service.create_or_update_job(
        payload=patch_data,
        actor_user_id=ctx.user_id,
        actor_role="customer",
        customer_id=ctx.customer_id,
    )
    return JobRequestOut.model_validate(updated)


@router.post(
    "/{job_id}/close",
    response_model=JobRequestOut,
    summary="Close a job listing",
)
async def close_job(
    job_id: str,
    ctx: RequireCustomer,
    service: Annotated[JobRequestService, Depends(get_job_request_service)],
) -> JobRequestOut:
    updated = await service.create_or_update_job(
        payload={"id": job_id, "status": "rejected", "accepted": False},
        actor_user_id=ctx.user_id,
        actor_role="customer",
        customer_id=ctx.customer_id,
    )
    return JobRequestOut.model_validate(updated)


@router.post(
    "/{job_id}/bid",
    response_model=JobRequestOut,
    summary="Provider places a bid on an open job",
)
async def bid_on_job(
    job_id: str,
    body: JobBidBody,
    ctx: RequireProvider,
    service: Annotated[JobRequestService, Depends(get_job_request_service)],
) -> JobRequestOut:
    assert ctx.provider_id is not None
    updated = await service.submit_bid(
        job_id=job_id,
        provider_id=ctx.provider_id,
        bid_data=body.model_dump(exclude_unset=True),
    )
    return JobRequestOut.model_validate(updated)


@router.post(
    "/{job_id}/pay",
    summary="Mark job request as paid",
)
async def mark_job_paid(
    job_id: str,
    service: Annotated[JobRequestService, Depends(get_job_request_service)],
) -> dict[str, Any]:
    await service.mark_as_paid(job_id)
    return {"status": "ok", "job_id": job_id, "is_paid": True}


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Customer deletes their job request",
)
async def delete_job(
    job_id: str,
    ctx: RequireCustomer,
    service: Annotated[JobRequestService, Depends(get_job_request_service)],
) -> None:
    assert ctx.customer_id is not None
    await service.delete_job(job_id=job_id, customer_id=ctx.customer_id)
