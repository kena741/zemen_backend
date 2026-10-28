"""Atomic like/unlike. The client never supplies the liked-user list."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import Service


async def _locked(db: AsyncSession, service_id: UUID) -> Service | None:
    return (
        await db.execute(select(Service).where(Service.id == service_id).with_for_update())
    ).scalar_one_or_none()


async def set_like(db: AsyncSession, service_id: UUID, user_id: UUID, *, liked: bool) -> Service | None:
    row = await _locked(db, service_id)
    if row is None:
        return None
    current = list(row.liked_user or [])
    key = str(user_id)
    if liked and key not in current:
        current.append(key)
    if not liked and key in current:
        current = [u for u in current if u != key]
    row.liked_user = current
    await db.flush()
    await db.refresh(row)
    return row
