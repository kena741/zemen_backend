from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.notification import NotificationBulkResult, NotificationIdsBody, NotificationOut
from app.core.security.deps import RequireAuth
from app.core.services import notification_service
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get(
    "",
    response_model=Page[NotificationOut],
    operation_id="notifications_list_mine",
    summary="List notifications for linked customer/provider/handyman profiles",
)
async def list_mine(
    ctx: RequireAuth,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[NotificationOut]:
    rows = await notification_service.list_for_actor(
        db,
        customer_id=ctx.customer_id,
        provider_id=ctx.provider_id,
        handyman_id=ctx.handyman_id,
        limit=limit,
        offset=offset,
    )
    return Page(
        items=[NotificationOut.model_validate(r) for r in rows],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.post(
    "/read",
    response_model=NotificationBulkResult,
    operation_id="notifications_mark_read",
    summary="Mark own notifications read (all unread, or the given ids)",
)
async def mark_read(
    body: NotificationIdsBody,
    ctx: RequireAuth,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationBulkResult:
    count = await notification_service.mark_read(
        db,
        user_id=ctx.user_id,
        customer_id=ctx.customer_id,
        provider_id=ctx.provider_id,
        handyman_id=ctx.handyman_id,
        ids=body.ids,
    )
    return NotificationBulkResult(count=count)


@router.delete(
    "/{notification_id}",
    response_model=NotificationBulkResult,
    operation_id="notifications_delete_one",
    summary="Delete one notification the caller owns",
)
async def delete_one(
    notification_id: UUID,
    ctx: RequireAuth,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationBulkResult:
    count = await notification_service.delete_owned(
        db,
        user_id=ctx.user_id,
        customer_id=ctx.customer_id,
        provider_id=ctx.provider_id,
        handyman_id=ctx.handyman_id,
        ids=[notification_id],
    )
    return NotificationBulkResult(count=count)


@router.delete(
    "",
    response_model=NotificationBulkResult,
    operation_id="notifications_clear_mine",
    summary="Delete all notifications the caller owns",
)
async def clear_mine(
    ctx: RequireAuth,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationBulkResult:
    count = await notification_service.delete_owned(
        db,
        user_id=ctx.user_id,
        customer_id=ctx.customer_id,
        provider_id=ctx.provider_id,
        handyman_id=ctx.handyman_id,
        ids=None,
    )
    return NotificationBulkResult(count=count)
