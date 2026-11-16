from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.notification import (
    NotificationBulkResult,
    NotificationCreate,
    NotificationIdsBody,
    NotificationOut,
    PushNotificationSend,
    UnreadCountOut,
)
from app.core.security.deps import AuthContext, RequireAuth
from app.core.services.notification_service import NotificationService
from app.persistence.repositories.notification_repo import NotificationRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def get_notification_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationService:
    return NotificationService(NotificationRepository(db))


def _actor_ids(ctx: AuthContext) -> list[UUID]:
    ids: list[UUID] = []
    if ctx.customer_id is not None:
        ids.append(ctx.customer_id)
    if ctx.provider_id is not None:
        ids.append(ctx.provider_id)
    if ctx.handyman_id is not None:
        ids.append(ctx.handyman_id)
    if ctx.user_id is not None and ctx.user_id not in ids:
        ids.append(ctx.user_id)
    return ids


@router.get(
    "",
    response_model=Page[NotificationOut],
    operation_id="notifications_list_mine",
    summary="List notifications for linked customer/provider/handyman profiles",
)
async def list_mine(
    ctx: RequireAuth,
    service: Annotated[NotificationService, Depends(get_notification_service)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[NotificationOut]:
    actor_ids = _actor_ids(ctx)
    rows = await service.list_notifications(actor_id=actor_ids, limit=limit, offset=offset)
    return Page(
        items=[NotificationOut.model_validate(r) for r in rows],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.get(
    "/unread/count",
    response_model=UnreadCountOut,
    summary="Get count of unread notifications for caller",
)
async def get_unread_count(
    ctx: RequireAuth,
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> UnreadCountOut:
    actor_ids = _actor_ids(ctx)
    cnt = await service.get_unread_count(actor_ids)
    return UnreadCountOut(unread_count=cnt)


@router.post(
    "",
    response_model=NotificationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create or upsert notification (setNotification)",
)
async def create_notification(
    body: NotificationCreate,
    ctx: RequireAuth,
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationOut:
    data = body.model_dump(exclude_unset=True)
    if not data.get("customer_id") and ctx.customer_id:
        data["customer_id"] = ctx.customer_id
    if not data.get("provider_id") and ctx.provider_id:
        data["provider_id"] = ctx.provider_id
    created = await service.create_notification(data)
    return NotificationOut.model_validate(created)


@router.post(
    "/read",
    response_model=NotificationBulkResult,
    operation_id="notifications_mark_read",
    summary="Mark own notifications read (all unread, or the given ids)",
)
async def mark_read(
    body: NotificationIdsBody,
    ctx: RequireAuth,
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationBulkResult:
    actor_ids = _actor_ids(ctx)
    if body.ids:
        count = await service.mark_ids_read(actor_id=actor_ids, ids=body.ids)
    else:
        count = await service.mark_all_read(actor_id=actor_ids)
    return NotificationBulkResult(count=count)


@router.post(
    "/send-push",
    summary="Dispatch FCM push notification",
)
async def send_push_notification(
    body: PushNotificationSend,
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> dict[str, bool]:
    success = await service.send_push_notification(
        fcm_token=body.token,
        title=body.title,
        body=body.body,
        data=body.payload,
    )
    return {"success": success}


@router.delete(
    "/{notification_id}",
    response_model=NotificationBulkResult,
    operation_id="notifications_delete_one",
    summary="Delete one notification the caller owns",
)
async def delete_one(
    notification_id: UUID,
    ctx: RequireAuth,
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationBulkResult:
    actor_ids = _actor_ids(ctx)
    count = await service.delete_notifications(actor_id=actor_ids, ids=[notification_id])
    return NotificationBulkResult(count=count)


@router.delete(
    "",
    response_model=NotificationBulkResult,
    operation_id="notifications_clear_mine",
    summary="Delete all notifications the caller owns",
)
async def clear_mine(
    ctx: RequireAuth,
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationBulkResult:
    actor_ids = _actor_ids(ctx)
    count = await service.delete_notifications(actor_id=actor_ids, ids=None)
    return NotificationBulkResult(count=count)
