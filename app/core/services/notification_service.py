"""Service for Notifications and Firebase Cloud Messaging (FCM) dispatch.

Also provides module-level functions for direct database interaction and backwards-compatibility.
"""

from __future__ import annotations

from datetime import UTC, datetime
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import EntityNotFoundError
from app.domain.notification import NotificationDomain
from app.persistence.repositories.notification_repo import NotificationRepository
from app.persistence.sqlalchemy.models import Notification

logger = logging.getLogger(__name__)


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


class NotificationService:
    def __init__(self, notif_repo: NotificationRepository) -> None:
        self.notif_repo = notif_repo

    async def list_notifications(
        self, actor_id: list[UUID] | UUID, limit: int = 50, offset: int = 0
    ) -> list[NotificationDomain]:
        return await self.notif_repo.list_for_actor(actor_id=actor_id, limit=limit, offset=offset)

    async def create_notification(self, data: dict[str, Any]) -> NotificationDomain:
        return await self.notif_repo.create_notification(data)

    async def mark_read(self, notification_id: UUID) -> bool:
        marked = await self.notif_repo.mark_as_read(notification_id)
        if not marked:
            raise EntityNotFoundError("Notification", notification_id)
        return True

    async def mark_ids_read(self, actor_id: list[UUID] | UUID, ids: list[UUID]) -> int:
        return await self.notif_repo.mark_ids_read(actor_id=actor_id, ids=ids)

    async def mark_all_read(self, actor_id: list[UUID] | UUID) -> int:
        return await self.notif_repo.mark_all_read(actor_id=actor_id)

    async def delete_notifications(
        self, actor_id: list[UUID] | UUID, ids: list[UUID] | None = None
    ) -> int:
        return await self.notif_repo.delete_owned(actor_id=actor_id, ids=ids)

    async def get_unread_count(self, actor_id: list[UUID] | UUID) -> int:
        return await self.notif_repo.count_unread(actor_id=actor_id)

    async def send_push_notification(
        self,
        fcm_token: str | None,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> bool:
        if not fcm_token:
            return False

        try:
            import firebase_admin
            from firebase_admin import messaging

            # If Firebase App initialized, send push
            if firebase_admin._apps:
                msg = messaging.Message(
                    notification=messaging.Notification(title=title, body=body),
                    data=data or {},
                    token=fcm_token,
                )
                messaging.send(msg)
                return True
        except Exception as e:
            logger.warning("FCM push send failed: %s", e)
            return False
        return True
