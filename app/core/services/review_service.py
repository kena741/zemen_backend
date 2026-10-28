from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services import booking_service
from app.persistence.sqlalchemy.models import ReviewCustomer


async def list_reviews(
    db: AsyncSession,
    *,
    service_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ReviewCustomer]:
    stmt = select(ReviewCustomer)
    if service_id is not None:
        stmt = stmt.where(ReviewCustomer.service_id == service_id)
    stmt = stmt.order_by(ReviewCustomer.date.desc()).limit(min(limit, 100)).offset(max(offset, 0))
    return list((await db.execute(stmt)).scalars().all())


async def create_review(
    db: AsyncSession,
    *,
    customer_id: UUID,
    comment: str,
    rating: str | None,
    service_id: UUID | None,
    booking_id: UUID | None,
) -> ReviewCustomer:
    if booking_id is not None:
        booking = await booking_service.get_booking(db, booking_id)
        if booking is None or booking.customer_id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Booking not found for customer",
            )
        if service_id is None:
            service_id = booking.service_id

    row = ReviewCustomer(
        id=uuid4(),
        comment=comment,
        customer_id=customer_id,
        date=datetime.now(UTC),
        rating=rating,
        service_id=service_id,
        booking_id=booking_id,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row
