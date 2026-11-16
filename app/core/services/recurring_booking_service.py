"""Service for recurring booking cycle monitoring and notification triggers."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models.booking import BookedService


class RecurringBookingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def scan_and_notify_due_cycles(self) -> int:
        now = datetime.now(timezone.utc)
        stmt = (
            update(BookedService)
            .where(
                BookedService.current_period_end.is_not(None),
                BookedService.current_period_end <= now,
                BookedService.next_cycle_due.is_(False),
                BookedService.is_archived.is_(False),
            )
            .values(
                next_cycle_due=True,
                next_cycle_notified_at=now,
            )
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.rowcount or 0

