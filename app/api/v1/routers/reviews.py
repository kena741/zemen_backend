from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.review import ReviewCreate, ReviewOut
from app.core.security.deps import RequireCustomer
from app.core.services import review_service
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.get(
    "",
    response_model=Page[ReviewOut],
    operation_id="reviews_list",
    summary="List customer reviews (optionally filter by service)",
)
async def list_reviews(
    db: Annotated[AsyncSession, Depends(get_db)],
    service_id: UUID | None = Query(None, alias="serviceId"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[ReviewOut]:
    rows = await review_service.list_reviews(
        db, service_id=service_id, limit=limit, offset=offset
    )
    return Page(
        items=[ReviewOut.model_validate(r) for r in rows],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.post(
    "",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="reviews_create",
    summary="Create a review for the authenticated customer",
)
async def create_review(
    body: ReviewCreate,
    ctx: RequireCustomer,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReviewOut:
    assert ctx.customer_id is not None
    row = await review_service.create_review(
        db,
        customer_id=ctx.customer_id,
        comment=body.comment,
        rating=body.rating,
        service_id=body.service_id,
        booking_id=body.booking_id,
    )
    return ReviewOut.model_validate(row)
