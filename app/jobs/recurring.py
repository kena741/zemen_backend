"""Recurring cycle due — SELECT-only until PAYMENTS_WRITES_ENABLED.

Does not call Chapa or write wallets. Edge `notify-recurring-cycle-due` stays live.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import BookedService


async def list_due_cycles(db: AsyncSession, *, limit: int = 100) -> list[BookedService]:
    stmt = (
        select(BookedService)
        .where(
            BookedService.next_cycle_due.is_(True),
            BookedService.is_archived.is_(False),
        )
        .order_by(BookedService.current_period_end.asc().nulls_last())
        .limit(min(limit, 500))
    )
    return list((await db.execute(stmt)).scalars().all())
