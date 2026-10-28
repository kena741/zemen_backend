from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import BookedService


async def list_bookings_for_customer(
    db: AsyncSession,
    customer_id: UUID,
    *,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[BookedService]:
    stmt = select(BookedService).where(BookedService.customer_id == customer_id)
    if not include_archived:
        stmt = stmt.where(BookedService.is_archived.is_(False))
    stmt = stmt.order_by(BookedService.created_at.desc()).limit(min(limit, 100)).offset(max(offset, 0))
    return list((await db.execute(stmt)).scalars().all())


async def list_bookings_for_provider(
    db: AsyncSession,
    provider_id: UUID,
    *,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[BookedService]:
    stmt = select(BookedService).where(BookedService.provider_id == provider_id)
    if not include_archived:
        stmt = stmt.where(BookedService.is_archived.is_(False))
    stmt = stmt.order_by(BookedService.created_at.desc()).limit(min(limit, 100)).offset(max(offset, 0))
    return list((await db.execute(stmt)).scalars().all())


async def get_booking(db: AsyncSession, booking_id: UUID) -> BookedService | None:
    return (
        await db.execute(select(BookedService).where(BookedService.id == booking_id))
    ).scalar_one_or_none()


def actor_can_view_booking(
    booking: BookedService,
    *,
    user_id: UUID,
    customer_id: UUID | None,
    provider_id: UUID | None,
) -> bool:
    if customer_id is not None and booking.customer_id == customer_id:
        return True
    if provider_id is not None and booking.provider_id == provider_id:
        return True
    if booking.customer_user_id == user_id or booking.provider_user_id == user_id:
        return True
    return False
