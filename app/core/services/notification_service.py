"""Service for Notifications and Firebase Cloud Messaging (FCM) dispatch."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.domain.exceptions import EntityNotFoundError
from app.domain.notification import NotificationDomain
from app.persistence.repositories.notification_repo import NotificationRepository

logger = logging.getLogger(__name__)


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
