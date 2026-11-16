"""Lifecycle state transitions, OTP verification, service proof, and decline refunds."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.domain.booking import BookingDomain
from app.domain.exceptions import (
    EntityNotFoundError,
    PermissionDeniedError,
    StateTransitionError,
    ValidationError,
)
from app.persistence.repositories.handyman_repo import HandymanRepository
from app.persistence.repositories.mobile_booking_repo import MobileBookingRepository

# Allowed lifecycle state transitions by actor role
PROVIDER_TRANSITIONS = {
    "pending": {"accepted", "declined"},
    "accepted": {"on_going", "in_progress"},
    "on_going": {"hold", "completed"},
    "in_progress": {"hold", "completed"},
    "hold": {"on_going", "in_progress"},
}

CUSTOMER_TRANSITIONS = {
    "pending": {"cancelled"},
    "accepted": {"cancelled"},
}


class BookingLifecycleService:
    def __init__(
        self,
        booking_repo: MobileBookingRepository,
        handyman_repo: HandymanRepository,
    ) -> None:
        self.booking_repo = booking_repo
        self.handyman_repo = handyman_repo

    async def transition_status(
        self,
        booking_id: UUID,
        actor_role: str,
        actor_id: UUID,
        new_status: str,
        reason: str | None = None,
        otp: str | None = None,
    ) -> BookingDomain:
        booking = await self.booking_repo.get_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError("Booking", booking_id)

        current_status = booking.status or "pending"
        new_status = new_status.lower().strip()

        # Check permissions & allowed transition graph
        if actor_role == "provider":
            if booking.provider_id != actor_id:
                raise PermissionDeniedError("You do not own this booking.")
            allowed = PROVIDER_TRANSITIONS.get(current_status, set())
            if new_status not in allowed:
                raise StateTransitionError(
                    current_status,
                    new_status,
                    f"Provider is not allowed to transition booking from '{current_status}' to '{new_status}'.",
                )
        elif actor_role == "customer":
            if booking.customer_id != actor_id:
                raise PermissionDeniedError("You do not own this booking.")
            allowed = CUSTOMER_TRANSITIONS.get(current_status, set())
            if new_status not in allowed:
                raise StateTransitionError(
                    current_status,
                    new_status,
                    f"Customer is not allowed to transition booking from '{current_status}' to '{new_status}'.",
                )
        elif actor_role == "admin":
            # Admin can transition freely
            pass
        else:
            raise PermissionDeniedError("Unknown actor role.")

        now = datetime.now(timezone.utc)
        updates: dict[str, Any] = {"status": new_status}

        if reason:
            updates["reason"] = reason

        # Operational timestamp / timer updates
        if new_status in {"on_going", "in_progress"}:
            if current_status == "accepted":
                updates["start_time"] = now
            elif current_status == "hold":
                # Resume from hold
                hold_records = list(booking.hold_time or [])
                if hold_records:
                    last_hold = dict(hold_records[-1])
                    last_hold["resumed_at"] = now.isoformat()
                    hold_records[-1] = last_hold
                    updates["hold_time"] = hold_records

        elif new_status == "hold":
            hold_records = list(booking.hold_time or [])
            hold_records.append({"held_at": now.isoformat(), "reason": reason})
            updates["hold_time"] = hold_records

        elif new_status == "completed":
            # OTP verification check if OTP was set on the booking
            if booking.otp:
                if not otp or otp.strip() != booking.otp.strip():
                    raise ValidationError("Invalid or missing completion OTP.")
            updates["end_time"] = now
            updates["payment_status"] = "payment_completed"
            updates["payment_completed"] = True

        updated = await self.booking_repo.update_booking_fields(booking_id, updates)
        if not updated:
            raise EntityNotFoundError("Booking", booking_id)
        return updated

    async def assign_handyman(
        self,
        booking_id: UUID,
        provider_id: UUID,
        handyman_id: UUID,
    ) -> BookingDomain:
        booking = await self.booking_repo.get_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError("Booking", booking_id)
        if booking.provider_id != provider_id:
            raise PermissionDeniedError("You do not own this booking.")

        # Validate handyman ownership
        hm = await self.handyman_repo.get_by_id(handyman_id)
        if not hm or hm.provider_id != provider_id:
            raise EntityNotFoundError("Handyman personnel", handyman_id)

        updated = await self.booking_repo.update_booking_fields(
            booking_id, {"handyman_id": handyman_id}
        )
        if not updated:
            raise EntityNotFoundError("Booking", booking_id)
        return updated

    async def verify_otp(self, booking_id: UUID, otp: str) -> bool:
        booking = await self.booking_repo.get_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError("Booking", booking_id)
        if not booking.otp:
            return True
        return booking.otp.strip() == otp.strip()

    async def update_service_proof(
        self,
        booking_id: UUID,
        provider_id: UUID,
        proof_data: dict[str, Any],
    ) -> BookingDomain:
        booking = await self.booking_repo.get_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError("Booking", booking_id)
        if booking.provider_id != provider_id:
            raise PermissionDeniedError("You do not own this booking.")

        now = datetime.now(timezone.utc)
        updated = await self.booking_repo.update_booking_fields(
            booking_id,
            {
                "service_proof": proof_data,
                "service_proof_updated_at": now,
            },
        )
        if not updated:
            raise EntityNotFoundError("Booking", booking_id)
        return updated

    async def refund_on_decline(
        self,
        booking_id: UUID,
        provider_id: UUID,
    ) -> dict[str, Any]:
        """Edge function refund-customer-booking-decline equivalent in Python service layer."""
        booking = await self.booking_repo.get_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError("Booking", booking_id)
        if booking.provider_id != provider_id:
            raise PermissionDeniedError("You do not own this booking.")

        if not booking.customer_id:
            return {"status": "skipped", "message": "No customer ID associated with this booking."}

        # Check idempotency: has this booking already been refunded?
        if await self.booking_repo.has_refund_transaction(booking_id):
            return {
                "status": "already_refunded",
                "message": f"Refund for booking {booking_id} was already processed.",
            }

        escrow_amt = await self.booking_repo.get_escrow_amount(booking_id)
        if not escrow_amt or escrow_amt <= 0:
            # Check total_amount from booking if payment record not populated
            if booking.payment_completed and booking.total_amount:
                escrow_amt = Decimal(str(booking.total_amount))
            else:
                return {
                    "status": "no_charge",
                    "message": "No paid escrow amount found for this booking.",
                }

        await self.booking_repo.credit_customer_wallet_refund(
            customer_id=booking.customer_id,
            customer_user_id=booking.customer_user_id,
            booking_id=booking_id,
            amount=escrow_amt,
            note=f"Refund for declined booking {booking_id}",
        )
        return {
            "status": "success",
            "refunded_amount": float(escrow_amt),
            "booking_id": str(booking_id),
        }

