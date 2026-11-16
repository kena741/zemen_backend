"""Customer Reviews endpoints and ratings aggregation."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.review import ReviewCreate, ReviewOut
from app.core.security.deps import RequireCustomer
from app.core.services.review_service import ReviewService
from app.persistence.repositories.mobile_booking_repo import MobileBookingRepository
from app.persistence.repositories.review_repo import ReviewRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/reviews", tags=["Reviews"])


def get_review_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReviewService:
    return ReviewService(
        review_repo=ReviewRepository(db),
        booking_repo=MobileBookingRepository(db),
    )


@router.get(
    "",
    response_model=Page[ReviewOut],
    summary="List customer reviews (filter by service)",
)
async def list_reviews(
    service: Annotated[ReviewService, Depends(get_review_service)],
    service_id: UUID | None = Query(None, alias="serviceId"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[ReviewOut]:
    if service_id:
        rows = await service.list_service_reviews(service_id=service_id, limit=limit, offset=offset)
    else:
        rows = []
    return Page(
        items=[ReviewOut.model_validate(r) for r in rows],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.get(
    "/by-booking/{booking_id}",
    response_model=ReviewOut | None,
    summary="Get review associated with a booking ID",
)
async def get_booking_review(
    booking_id: UUID,
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> ReviewOut | None:
    review = await service.get_by_booking_id(booking_id)
    return ReviewOut.model_validate(review) if review else None


@router.post(
    "",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create customer review and update service ratings aggregate",
)
async def create_review(
    body: ReviewCreate,
    ctx: RequireCustomer,
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> ReviewOut:
    assert ctx.customer_id is not None
    created = await service.add_review(
        customer_id=ctx.customer_id,
        payload=body.model_dump(exclude_unset=True),
    )
    return ReviewOut.model_validate(created)
