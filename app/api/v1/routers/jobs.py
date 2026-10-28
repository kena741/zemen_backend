from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.job import JobBidBody, JobCreate, JobPatch, JobRequestOut
from app.core.security.deps import RequireAuth, RequireCustomer, RequireProvider
from app.core.services import job_service
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get(
    "",
    response_model=Page[JobRequestOut],
    operation_id="jobs_list_mine",
    summary="List job requests for customer or provider profile",
)
async def list_mine(
    ctx: RequireAuth,
    db: Annotated[AsyncSession, Depends(get_db)],
    as_role: Literal["customer", "provider"] = Query("customer", alias="as"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[JobRequestOut]:
    if as_role == "customer":
        if ctx.customer_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Customer profile required")
        rows = await job_service.list_jobs_for_customer(
            db, ctx.customer_id, limit=limit, offset=offset
        )
    else:
        if ctx.provider_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Provider profile required")
        rows = await job_service.list_jobs_for_provider(
            db, ctx.provider_id, limit=limit, offset=offset
        )
    return Page(
        items=[JobRequestOut.model_validate(r) for r in rows],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.post(
    "",
    response_model=JobRequestOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="jobs_create",
    summary="Create or upsert a customer job listing (status accepted = open; is_paid ignored)",
)
async def create_job(
    body: JobCreate,
    ctx: RequireCustomer,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JobRequestOut:
    assert ctx.customer_id is not None
    row = await job_service.create_job(
        db, customer_id=ctx.customer_id, data=body.model_dump(exclude_unset=True)
    )
    return JobRequestOut.model_validate(row)


@router.patch(
    "/{job_id}",
    response_model=JobRequestOut,
    operation_id="jobs_patch",
    summary="Customer patch of listing fields (never is_paid)",
)
async def patch_job(
    job_id: str,
    body: JobPatch,
    ctx: RequireCustomer,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JobRequestOut:
    assert ctx.customer_id is not None
    row = await job_service.update_job(
        db, job_id=job_id, customer_id=ctx.customer_id, patch=body.model_dump(exclude_unset=True)
    )
    return JobRequestOut.model_validate(row)


@router.post(
    "/{job_id}/close",
    response_model=JobRequestOut,
    operation_id="jobs_close",
    summary="Close a job listing (enum status rejected)",
)
async def close_job(
    job_id: str,
    ctx: RequireCustomer,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JobRequestOut:
    assert ctx.customer_id is not None
    row = await job_service.close_job(db, job_id=job_id, customer_id=ctx.customer_id)
    return JobRequestOut.model_validate(row)


@router.post(
    "/{job_id}/bid",
    response_model=JobRequestOut,
    operation_id="jobs_bid",
    summary="Provider bid on an open job (does not assign the listing)",
)
async def bid_on_job(
    job_id: str,
    body: JobBidBody,
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JobRequestOut:
    row = await job_service.add_bid(
        db, job_id=job_id, user_id=ctx.user_id, bid_price=body.bid_price, note=body.note
    )
    return JobRequestOut.model_validate(row)
