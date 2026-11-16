"""Repository for Notifications."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.notification import NotificationDomain
from app.persistence.sqlalchemy.models.social import Notification


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def to_domain(self, entity: Notification) -> NotificationDomain:
        return NotificationDomain(
            id=entity.id,
            title=entity.title,
            description=entity.description,
            type=entity.type,
            is_read=entity.is_read,
            recipient_role=entity.recipient_role,
            created_at=entity.created_at or datetime.now(timezone.utc),
            read_at=entity.read_at,
            booking_id=entity.booking_id,
            action_url=entity.action_url,
            sender_id=entity.sender_id,
            customer_id=entity.customer_id,
            provider_id=entity.provider_id,
            handyman_id=entity.handyman_id,
        )

    async def create_notification(self, data: dict[str, Any]) -> NotificationDomain:
        now = datetime.now(timezone.utc)
        entity = Notification(
            id=data.get("id") or uuid4(),
            title=data.get("title"),
            description=data.get("description"),
            type=data.get("type", "general"),
            is_read=False,
            recipient_role=data.get("recipient_role", "customer"),
            created_at=now,
            booking_id=data.get("booking_id"),
            action_url=data.get("action_url"),
            sender_id=data.get("sender_id"),
            customer_id=data.get("customer_id"),
            provider_id=data.get("provider_id"),
            handyman_id=data.get("handyman_id"),
        )
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return self.to_domain(entity)

    def _actor_filter(self, actor_ids: list[UUID] | UUID):
        ids = [actor_ids] if isinstance(actor_ids, UUID) else [i for i in actor_ids if i is not None]
        if not ids:
            return None
        return or_(
            Notification.customer_id.in_(ids),
            Notification.provider_id.in_(ids),
            Notification.handyman_id.in_(ids),
        )

    async def list_for_actor(
        self,
        actor_id: list[UUID] | UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[NotificationDomain]:
        filt = self._actor_filter(actor_id)
        if filt is None:
            return []
        stmt = (
            select(Notification)
            .where(filt)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return [self.to_domain(n) for n in res.scalars().all()]

    async def mark_as_read(self, notification_id: UUID) -> bool:
        now = datetime.now(timezone.utc)
        stmt = (
            update(Notification)
            .where(Notification.id == notification_id)
            .values(is_read=True, read_at=now)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return bool(res.rowcount and res.rowcount > 0)

    async def mark_ids_read(self, actor_id: list[UUID] | UUID, ids: list[UUID]) -> int:
        if not ids:
            return 0
        filt = self._actor_filter(actor_id)
        if filt is None:
            return 0
        now = datetime.now(timezone.utc)
        stmt = (
            update(Notification)
            .where(filt, Notification.id.in_(ids), Notification.is_read.is_(False))
            .values(is_read=True, read_at=now)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return int(res.rowcount or 0)

    async def mark_all_read(self, actor_id: list[UUID] | UUID) -> int:
        filt = self._actor_filter(actor_id)
        if filt is None:
            return 0
        now = datetime.now(timezone.utc)
        stmt = (
            update(Notification)
            .where(filt, Notification.is_read.is_(False))
            .values(is_read=True, read_at=now)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return int(res.rowcount or 0)

    async def delete_owned(
        self,
        actor_id: list[UUID] | UUID,
        ids: list[UUID] | None = None,
    ) -> int:
        filt = self._actor_filter(actor_id)
        if filt is None:
            return 0
        stmt = select(Notification).where(filt)
        if ids:
            stmt = stmt.where(Notification.id.in_(ids))
        res = await self.session.execute(stmt)
        rows = list(res.scalars().all())
        for row in rows:
            await self.session.delete(row)
        await self.session.commit()
        return len(rows)

    async def count_unread(self, actor_id: list[UUID] | UUID) -> int:
        filt = self._actor_filter(actor_id)
        if filt is None:
            return 0
        stmt = select(func.count(Notification.id)).where(filt, Notification.is_read.is_(False))
        res = await self.session.execute(stmt)
        return int(res.scalar_one() or 0)
