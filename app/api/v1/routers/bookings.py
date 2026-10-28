from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.booking import BookingCreate, BookingOut
from app.api.v1.schemas.booking_actions import (
    AssignHandymanBody,
    CancelBookingBody,
    RejectBookingBody,
    SetBookingStatusBody,
)
from app.api.v1.schemas.common import Page, PageMeta
from app.core.security.deps import RequireAuth, RequireCustomer, RequireProvider
from app.core.services import booking_actions, booking_create, booking_service, profile_service
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.get(
    "",
    response_model=Page[BookingOut],
    operation_id="bookings_list_mine_customer",
    summary="List bookings for the authenticated customer",
)
async def list_my_customer_bookings(
    ctx: RequireCustomer,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_archived: bool = Query(False, alias="includeArchived"),
) -> Page[BookingOut]:
    assert ctx.customer_id is not None
    rows = await booking_service.list_bookings_for_customer(
        db,
        ctx.customer_id,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return Page(
        items=[BookingOut.model_validate(r) for r in rows],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.post(
    "",
    response_model=BookingOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="bookings_create",
    summary="Create an unpaid pending booking for the authenticated customer",
)
async def create_booking(
    body: BookingCreate,
    ctx: RequireCustomer,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BookingOut:
    assert ctx.customer_id is not None
    customer = await profile_service.get_customer_by_id(db, ctx.customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    row = await booking_create.create_customer_booking(
        db,
        customer=customer,
        auth_user_id=ctx.user_id,
        data=body.model_dump(),
    )
    return BookingOut.model_validate(row)


@router.get(
    "/{booking_id}",
    response_model=BookingOut,
    operation_id="bookings_get",
    summary="Get a booking if the caller owns it as customer or provider",
)
async def get_booking(
    booking_id: UUID,
    ctx: RequireAuth,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BookingOut:
    row = await booking_service.get_booking(db, booking_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if not booking_service.actor_can_view_booking(
        row,
        user_id=ctx.user_id,
        customer_id=ctx.customer_id,
        provider_id=ctx.provider_id,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return BookingOut.model_validate(row)


@router.post(
    "/{booking_id}/accept",
    response_model=BookingOut,
    operation_id="bookings_accept",
    summary="Provider accepts a pending booking",
)
async def accept_booking(
    booking_id: UUID,
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BookingOut:
    assert ctx.provider_id is not None
    row = await booking_actions.accept_booking(
        db, provider_id=ctx.provider_id, booking_id=booking_id
    )
    return BookingOut.model_validate(row)


@router.post(
    "/{booking_id}/reject",
    response_model=BookingOut,
    operation_id="bookings_reject",
    summary="Provider rejects a booking (status only — refunds still via Edge until Plan 4)",
)
async def reject_booking(
    booking_id: UUID,
    body: RejectBookingBody,
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BookingOut:
    assert ctx.provider_id is not None
    row = await booking_actions.reject_booking(
        db, provider_id=ctx.provider_id, booking_id=booking_id, reason=body.reason
    )
    return BookingOut.model_validate(row)


@router.post(
    "/{booking_id}/assign-handyman",
    response_model=BookingOut,
    operation_id="bookings_assign_handyman",
    summary="Assign an owned handyman to a booking",
)
async def assign_handyman(
    booking_id: UUID,
    body: AssignHandymanBody,
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BookingOut:
    assert ctx.provider_id is not None
    row = await booking_actions.assign_handyman(
        db,
        provider_id=ctx.provider_id,
        booking_id=booking_id,
        handyman_id=body.handyman_id,
    )
    return BookingOut.model_validate(row)


@router.post(
    "/{booking_id}/status",
    response_model=BookingOut,
    operation_id="bookings_set_status",
    summary="Provider status transition (allowlisted; no wallet side effects)",
)
async def set_booking_status(
    booking_id: UUID,
    body: SetBookingStatusBody,
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BookingOut:
    assert ctx.provider_id is not None
    row = await booking_actions.set_status(
        db,
        provider_id=ctx.provider_id,
        booking_id=booking_id,
        new_status=body.status,
    )
    return BookingOut.model_validate(row)


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingOut,
    operation_id="bookings_cancel",
    summary="Customer cancel (status + pending offers only — refunds stay on Edge until Plan 4)",
)
async def cancel_booking(
    booking_id: UUID,
    body: CancelBookingBody,
    ctx: RequireCustomer,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BookingOut:
    row = await booking_actions.cancel_booking(
        db,
        booking_id=booking_id,
        customer_id=ctx.customer_id,
        user_id=ctx.user_id,
        reason=body.reason,
    )
    return BookingOut.model_validate(row)
