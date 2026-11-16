"""Mobile Booking router supporting setOrder upserts, lifecycle management, and earnings."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.booking import (
    BookingCreate,
    BookingOut,
    MonthlyEarningsOut,
    ServiceProofBody,
    VerifyBookingOtpBody,
)
from app.api.v1.schemas.booking_actions import (
    AssignHandymanBody,
    CancelBookingBody,
    RejectBookingBody,
    SetBookingStatusBody,
)
from app.api.v1.schemas.common import Page, PageMeta
from app.core.security.deps import RequireAuth, RequireCustomer, RequireProvider
from app.core.services.booking_lifecycle_service import BookingLifecycleService
from app.core.services.mobile_booking_service import MobileBookingService
from app.core.services.recurring_booking_service import RecurringBookingService
from app.persistence.repositories.customer_repo import CustomerRepository
from app.persistence.repositories.handyman_repo import HandymanRepository
from app.persistence.repositories.mobile_booking_repo import MobileBookingRepository
from app.persistence.repositories.provider_repo import ProviderRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/bookings", tags=["Bookings"])


def get_mobile_booking_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MobileBookingService:
    return MobileBookingService(
        booking_repo=MobileBookingRepository(db),
        customer_repo=CustomerRepository(db),
        provider_repo=ProviderRepository(db),
    )


def get_booking_lifecycle_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BookingLifecycleService:
    return BookingLifecycleService(
        booking_repo=MobileBookingRepository(db),
        handyman_repo=HandymanRepository(db),
    )


def get_recurring_booking_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RecurringBookingService:
    return RecurringBookingService(session=db)


# ======================== Booking Creation & Queries ========================


@router.get(
    "",
    response_model=Page[BookingOut],
    summary="List bookings for the authenticated customer",
)
async def list_customer_bookings(
    ctx: RequireCustomer,
    service: Annotated[MobileBookingService, Depends(get_mobile_booking_service)],
    status: str | None = Query(None),
    include_archived: bool = Query(False, alias="includeArchived"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[BookingOut]:
    assert ctx.customer_id is not None
    rows = await service.list_customer_bookings(
        customer_id=ctx.customer_id,
        status=status,
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
    summary="Create or update booking (`setOrder` endpoint supporting dual casing)",
)
async def create_or_update_booking(
    body: BookingCreate,
    ctx: RequireAuth,
    service: Annotated[MobileBookingService, Depends(get_mobile_booking_service)],
) -> BookingOut:
    primary_role = "customer" if "customer" in ctx.roles else "provider"
    created = await service.create_or_update_booking(
        actor_user_id=ctx.user_id,
        actor_role=primary_role,
        payload=body.model_dump(exclude_unset=True),
        actor_customer_id=ctx.customer_id,
        actor_provider_id=ctx.provider_id,
    )
    return BookingOut.model_validate(created)


@router.get(
    "/provider",
    response_model=Page[BookingOut],
    summary="List bookings for the authenticated provider (with upcoming/completed filters)",
)
async def list_provider_bookings(
    ctx: RequireProvider,
    service: Annotated[MobileBookingService, Depends(get_mobile_booking_service)],
    status: str | None = Query(None),
    is_upcoming: bool = Query(False, alias="isUpcoming"),
    is_completed: bool = Query(False, alias="isCompleted"),
    include_archived: bool = Query(False, alias="includeArchived"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[BookingOut]:
    assert ctx.provider_id is not None
    rows = await service.list_provider_bookings(
        provider_id=ctx.provider_id,
        status=status,
        is_upcoming=is_upcoming,
        is_completed=is_completed,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return Page(
        items=[BookingOut.model_validate(r) for r in rows],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.get(
    "/provider/earnings/monthly",
    response_model=list[MonthlyEarningsOut],
    summary="Get monthly earnings aggregate for the authenticated provider",
)
async def get_provider_monthly_earnings(
    ctx: RequireProvider,
    service: Annotated[MobileBookingService, Depends(get_mobile_booking_service)],
    year: int | None = Query(None),
) -> list[MonthlyEarningsOut]:
    assert ctx.provider_id is not None
    earnings = await service.get_provider_monthly_earnings(provider_id=ctx.provider_id, year=year)
    return [MonthlyEarningsOut.model_validate(e) for e in earnings]


@router.get(
    "/{booking_id}",
    response_model=BookingOut,
    summary="Get single booking detail if owned by customer or provider",
)
async def get_booking_by_id(
    booking_id: UUID,
    ctx: RequireAuth,
    service: Annotated[MobileBookingService, Depends(get_mobile_booking_service)],
) -> BookingOut:
    primary_role = "admin" if "admin" in ctx.roles else ("customer" if "customer" in ctx.roles else "provider")
    item = await service.get_booking(
        booking_id=booking_id,
        actor_user_id=ctx.user_id,
        actor_role=primary_role,
        customer_id=ctx.customer_id,
        provider_id=ctx.provider_id,
    )
    return BookingOut.model_validate(item)


@router.delete(
    "/{booking_id}/unpaid",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete unpaid pending booking on payment cancellation",
)
async def delete_unpaid_pending_booking(
    booking_id: UUID,
    ctx: RequireCustomer,
    service: Annotated[MobileBookingService, Depends(get_mobile_booking_service)],
) -> None:
    assert ctx.customer_id is not None
    await service.delete_unpaid_pending(booking_id=booking_id, customer_id=ctx.customer_id)


# ======================== Lifecycle Transitions ========================


@router.post(
    "/{booking_id}/accept",
    response_model=BookingOut,
    summary="Provider accepts a pending booking",
)
async def accept_booking(
    booking_id: UUID,
    ctx: RequireProvider,
    lifecycle: Annotated[BookingLifecycleService, Depends(get_booking_lifecycle_service)],
) -> BookingOut:
    assert ctx.provider_id is not None
    updated = await lifecycle.transition_status(
        booking_id=booking_id,
        actor_role="provider",
        actor_id=ctx.provider_id,
        new_status="accepted",
    )
    return BookingOut.model_validate(updated)


@router.post(
    "/{booking_id}/reject",
    response_model=BookingOut,
    summary="Provider declines/rejects a booking",
)
@router.post(
    "/{booking_id}/decline",
    response_model=BookingOut,
    summary="Provider declines a booking",
)
async def decline_booking(
    booking_id: UUID,
    body: RejectBookingBody,
    ctx: RequireProvider,
    lifecycle: Annotated[BookingLifecycleService, Depends(get_booking_lifecycle_service)],
) -> BookingOut:
    assert ctx.provider_id is not None
    updated = await lifecycle.transition_status(
        booking_id=booking_id,
        actor_role="provider",
        actor_id=ctx.provider_id,
        new_status="declined",
        reason=body.reason,
    )
    return BookingOut.model_validate(updated)


@router.post(
    "/{booking_id}/assign-handyman",
    response_model=BookingOut,
    summary="Assign provider handyman to booking",
)
async def assign_handyman(
    booking_id: UUID,
    body: AssignHandymanBody,
    ctx: RequireProvider,
    lifecycle: Annotated[BookingLifecycleService, Depends(get_booking_lifecycle_service)],
) -> BookingOut:
    assert ctx.provider_id is not None
    updated = await lifecycle.assign_handyman(
        booking_id=booking_id,
        provider_id=ctx.provider_id,
        handyman_id=body.handyman_id,
    )
    return BookingOut.model_validate(updated)


@router.post(
    "/{booking_id}/status",
    response_model=BookingOut,
    summary="Provider updates booking lifecycle status (on_going, hold, completed)",
)
async def update_booking_status(
    booking_id: UUID,
    body: SetBookingStatusBody,
    ctx: RequireProvider,
    lifecycle: Annotated[BookingLifecycleService, Depends(get_booking_lifecycle_service)],
) -> BookingOut:
    assert ctx.provider_id is not None
    updated = await lifecycle.transition_status(
        booking_id=booking_id,
        actor_role="provider",
        actor_id=ctx.provider_id,
        new_status=body.status,
        reason=body.reason,
        otp=body.otp,
    )
    return BookingOut.model_validate(updated)


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingOut,
    summary="Customer cancels booking",
)
async def cancel_booking(
    booking_id: UUID,
    body: CancelBookingBody,
    ctx: RequireCustomer,
    lifecycle: Annotated[BookingLifecycleService, Depends(get_booking_lifecycle_service)],
) -> BookingOut:
    assert ctx.customer_id is not None
    updated = await lifecycle.transition_status(
        booking_id=booking_id,
        actor_role="customer",
        actor_id=ctx.customer_id,
        new_status="cancelled",
        reason=body.reason,
    )
    return BookingOut.model_validate(updated)


@router.post(
    "/{booking_id}/verify-otp",
    summary="Verify booking OTP for completion",
)
async def verify_booking_otp(
    booking_id: UUID,
    body: VerifyBookingOtpBody,
    lifecycle: Annotated[BookingLifecycleService, Depends(get_booking_lifecycle_service)],
) -> dict[str, Any]:
    valid = await lifecycle.verify_otp(booking_id=booking_id, otp=body.otp)
    return {"valid": valid}


@router.post(
    "/{booking_id}/service-proof",
    response_model=BookingOut,
    summary="Provider updates before/after service proof photos",
)
async def update_service_proof(
    booking_id: UUID,
    body: ServiceProofBody,
    ctx: RequireProvider,
    lifecycle: Annotated[BookingLifecycleService, Depends(get_booking_lifecycle_service)],
) -> BookingOut:
    assert ctx.provider_id is not None
    updated = await lifecycle.update_service_proof(
        booking_id=booking_id,
        provider_id=ctx.provider_id,
        proof_data=body.service_proof,
    )
    return BookingOut.model_validate(updated)


@router.post(
    "/{booking_id}/refund-on-decline",
    summary="Process customer wallet refund when provider declines paid booking",
)
async def refund_on_decline(
    booking_id: UUID,
    ctx: RequireProvider,
    lifecycle: Annotated[BookingLifecycleService, Depends(get_booking_lifecycle_service)],
) -> dict[str, Any]:
    assert ctx.provider_id is not None
    return await lifecycle.refund_on_decline(
        booking_id=booking_id,
        provider_id=ctx.provider_id,
    )


@router.post(
    "/recurring-cycle-due/scan",
    summary="Background scan: identify and notify bookings due for their next recurring cycle",
)
async def scan_recurring_cycles(
    recurring: Annotated[RecurringBookingService, Depends(get_recurring_booking_service)],
) -> dict[str, Any]:
    count = await recurring.scan_and_notify_due_cycles()
    return {"status": "ok", "flagged_count": count}
