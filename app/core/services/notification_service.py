from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import Notification


async def list_for_actor(
    db: AsyncSession,
    *,
    customer_id: UUID | None,
    provider_id: UUID | None,
    handyman_id: UUID | None,
    limit: int = 50,
    offset: int = 0,
) -> list[Notification]:
    clauses = []
    if customer_id is not None:
        clauses.append(Notification.customer_id == customer_id)
    if provider_id is not None:
        clauses.append(Notification.provider_id == provider_id)
    if handyman_id is not None:
        clauses.append(Notification.handyman_id == handyman_id)
    if not clauses:
        return []
    stmt = (
        select(Notification)
        .where(or_(*clauses))
        .order_by(Notification.created_at.desc())
        .limit(min(limit, 100))
        .offset(max(offset, 0))
    )
    return list((await db.execute(stmt)).scalars().all())


def _owner_filter(
    *,
    customer_id: UUID | None,
    provider_id: UUID | None,
    handyman_id: UUID | None,
    user_id: UUID,
):
    clauses = [Notification.customer_id == user_id, Notification.provider_id == user_id]
    if customer_id is not None:
        clauses.append(Notification.customer_id == customer_id)
    if provider_id is not None:
        clauses.append(Notification.provider_id == provider_id)
    if handyman_id is not None:
        clauses.append(Notification.handyman_id == handyman_id)
    return or_(*clauses)


async def mark_read(
    db: AsyncSession,
    *,
    user_id: UUID,
    customer_id: UUID | None,
    provider_id: UUID | None,
    handyman_id: UUID | None,
    ids: list[UUID] | None = None,
) -> int:
    stmt = select(Notification).where(
        _owner_filter(customer_id=customer_id, provider_id=provider_id, handyman_id=handyman_id, user_id=user_id),
        Notification.is_read.is_(False),
    )
    if ids:
        stmt = stmt.where(Notification.id.in_(ids))
    rows = list((await db.execute(stmt)).scalars().all())
    now = datetime.now(UTC)
    for row in rows:
        row.is_read = True
        row.read_at = now
    await db.flush()
    return len(rows)


async def delete_owned(
    db: AsyncSession,
    *,
    user_id: UUID,
    customer_id: UUID | None,
    provider_id: UUID | None,
    handyman_id: UUID | None,
    ids: list[UUID] | None = None,
) -> int:
    stmt = select(Notification).where(
        _owner_filter(customer_id=customer_id, provider_id=provider_id, handyman_id=handyman_id, user_id=user_id)
    )
    if ids:
        stmt = stmt.where(Notification.id.in_(ids))
    rows = list((await db.execute(stmt)).scalars().all())
    for row in rows:
        await db.delete(row)
    await db.flush()
    return len(rows)
