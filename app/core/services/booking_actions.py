"""Explicit booking lifecycle actions — no wallet / payment side effects."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.core.services import booking_service, handyman_service
from app.persistence.sqlalchemy.models import BookedService, ServiceOffer

# Allowed forward transitions for provider-driven flow (non-finance).
PROVIDER_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"accepted", "rejected"},
    "accepted": {"on_the_way", "in_progress", "hold", "rejected"},
    "on_the_way": {"in_progress", "hold", "completed"},
    "in_progress": {"hold", "completed", "pending_extra_payment"},
    "hold": {"in_progress", "on_the_way", "completed"},
    "pending_extra_payment": {"pending_approval", "in_progress"},
    "pending_approval": {"completed"},  # admin_paid stays admin-only
}

FINANCE_STATUSES = frozenset({"admin_paid", "completed"})  # completed may still need Edge for wallet


async def _load_provider_booking(
    db: AsyncSession, *, provider_id: UUID, booking_id: UUID
) -> BookedService:
    booking = await booking_service.get_booking(db, booking_id)
    if booking is None or booking.provider_id != provider_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return booking


async def accept_booking(
    db: AsyncSession, *, provider_id: UUID, booking_id: UUID
) -> BookedService:
    booking = await _load_provider_booking(db, provider_id=provider_id, booking_id=booking_id)
    current = (booking.status or "pending").lower()
    if current not in {"pending"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot accept booking in status '{booking.status}'",
        )
    booking.status = "accepted"
    await db.flush()
    await db.refresh(booking)
    return booking


async def reject_booking(
    db: AsyncSession, *, provider_id: UUID, booking_id: UUID, reason: str | None = None
) -> BookedService:
    """
    Sets status=rejected only.

    Refunds for paid bookings remain on Edge Function
    `refund-customer-booking-decline` until Plan 4.
    """
    booking = await _load_provider_booking(db, provider_id=provider_id, booking_id=booking_id)
    current = (booking.status or "pending").lower()
    if current not in {"pending", "accepted"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot reject booking in status '{booking.status}'",
        )
    booking.status = "rejected"
    if reason:
        booking.reason = reason
    await db.flush()
    await db.refresh(booking)
    return booking


async def assign_handyman(
    db: AsyncSession,
    *,
    provider_id: UUID,
    booking_id: UUID,
    handyman_id: UUID,
) -> BookedService:
    booking = await _load_provider_booking(db, provider_id=provider_id, booking_id=booking_id)
    handyman = await handyman_service.get_owned_handyman(db, provider_id, handyman_id)
    if handyman is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Handyman not found for provider")
    booking.handyman_id = handyman_id
    # Common app behavior: assigning often moves pending → accepted
    if (booking.status or "").lower() == "pending":
        booking.status = "accepted"
    await db.flush()
    await db.refresh(booking)
    return booking


async def set_status(
    db: AsyncSession,
    *,
    provider_id: UUID,
    booking_id: UUID,
    new_status: str,
) -> BookedService:
    target = new_status.strip().lower()
    if target in {"admin_paid"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin_paid is an admin-only transition",
        )
    booking = await _load_provider_booking(db, provider_id=provider_id, booking_id=booking_id)
    current = (booking.status or "pending").lower()
    allowed = PROVIDER_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Transition '{current}' → '{target}' is not allowed",
        )
    # Completing may require Edge `complete-booking` for commissions — document only.
    booking.status = target
    await db.flush()
    await db.refresh(booking)
    return booking


async def cancel_booking(
    db: AsyncSession,
    *,
    booking_id: UUID,
    customer_id: UUID | None,
    user_id: UUID,
    reason: str | None = None,
) -> BookedService:
    """Customer cancel. Status only — refunds stay on Edge until Plan 4."""
    booking = await booking_service.get_booking(db, booking_id)
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    owns = booking.customer_id == customer_id or booking.customer_user_id == user_id
    if not owns:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    current = (booking.status or "pending").lower()
    if current not in {"pending", "accepted"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel booking in status '{booking.status}'",
        )
    booking.status = "rejected"
    if reason:
        booking.reason = reason
    pending = (
        await db.execute(
            select(ServiceOffer).where(
                ServiceOffer.booking_id == str(booking.id),
                ServiceOffer.status == "pending",
            )
        )
    ).scalars().all()
    if not pending and booking.customer_id is not None:
        pending = (
            await db.execute(
                select(ServiceOffer).where(
                    ServiceOffer.customer_id.in_([str(booking.customer_id), str(user_id)]),
                    ServiceOffer.service_id == str(booking.service_id or ""),
                    ServiceOffer.status == "pending",
                )
            )
        ).scalars().all()
    for offer in pending:
        offer.status = "cancelled"
    await db.flush()
    await db.refresh(booking)
    return booking
