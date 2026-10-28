from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import JobRequest

JOB_PATCH_FIELDS = frozenset(
    {"title", "description", "price", "service_id", "service_model_list", "handyman_id"}
)


async def list_jobs_for_customer(db: AsyncSession, customer_id: UUID, *, limit: int = 50, offset: int = 0):
    stmt = (
        select(JobRequest)
        .where(JobRequest.customer_id == customer_id)
        .order_by(JobRequest.created_at.desc())
        .limit(min(limit, 100))
        .offset(max(offset, 0))
    )
    return list((await db.execute(stmt)).scalars().all())


async def list_jobs_for_provider(db: AsyncSession, provider_id: UUID, *, limit: int = 50, offset: int = 0):
    stmt = (
        select(JobRequest)
        .where(JobRequest.provider_id == provider_id)
        .order_by(JobRequest.created_at.desc())
        .limit(min(limit, 100))
        .offset(max(offset, 0))
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_job(db: AsyncSession, job_id: str) -> JobRequest | None:
    return (await db.execute(select(JobRequest).where(JobRequest.id == job_id))).scalar_one_or_none()


def _owns_customer(job: JobRequest, customer_id: UUID | None) -> bool:
    return customer_id is not None and job.customer_id == customer_id


async def create_job(db: AsyncSession, *, customer_id: UUID, data: dict[str, Any]) -> JobRequest:
    """Customer listing. Status `accepted` means open for bids (matches live app). `is_paid` is never client-set."""
    job_id = str(data.get("id") or uuid4())
    existing = await get_job(db, job_id)
    if existing is not None:
        if not _owns_customer(existing, customer_id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job id already exists")
        return await update_job(db, job_id=job_id, customer_id=customer_id, patch=data)

    now = datetime.now(UTC)
    row = JobRequest(
        id=job_id,
        created_at=now,
        accepted=False,
        status="accepted",
        is_paid=False,
        customer_id=customer_id,
        title=data.get("title"),
        description=data.get("description"),
        price=str(data["price"]) if data.get("price") is not None else None,
        service_id=data.get("service_id"),
        service_model_list=data.get("service_model_list"),
        provider_id=None,
        bid_list=[],
        bid_price=None,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def update_job(
    db: AsyncSession, *, job_id: str, customer_id: UUID, patch: dict[str, Any]
) -> JobRequest:
    job = await get_job(db, job_id)
    if job is None or not _owns_customer(job, customer_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    for key, value in patch.items():
        if key in JOB_PATCH_FIELDS:
            setattr(job, key, value)
    await db.flush()
    await db.refresh(job)
    return job


async def close_job(db: AsyncSession, *, job_id: str, customer_id: UUID) -> JobRequest:
    job = await get_job(db, job_id)
    if job is None or not _owns_customer(job, customer_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    job.status = "rejected"
    job.accepted = False
    await db.flush()
    await db.refresh(job)
    return job


async def add_bid(
    db: AsyncSession,
    *,
    job_id: str,
    user_id: UUID,
    bid_price: str,
    note: str | None = None,
) -> JobRequest:
    """Append or replace the caller's bid. Does not assign `provider_id` (that hides the listing)."""
    job = await get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if (job.status or "").lower() == "rejected":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job is closed")
    bidder = str(user_id)
    entry = {
        "providerId": bidder,
        "price": bid_price,
        "createdAt": datetime.now(UTC).isoformat(),
    }
    if note:
        entry["note"] = note
    bids = [b for b in list(job.bid_list or []) if (b or {}).get("providerId") != bidder]
    bids.append(entry)
    job.bid_list = bids
    job.bid_price = bid_price
    await db.flush()
    await db.refresh(job)
    return job
