"""Service for Customer Reviews and service ratings."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.domain.exceptions import EntityConflictError, EntityNotFoundError, ValidationError
from app.domain.review import ReviewCustomerDomain
from app.persistence.repositories.mobile_booking_repo import MobileBookingRepository
from app.persistence.repositories.review_repo import ReviewRepository


class ReviewService:
    def __init__(
        self,
        review_repo: ReviewRepository,
        booking_repo: MobileBookingRepository,
    ) -> None:
        self.review_repo = review_repo
        self.booking_repo = booking_repo

    async def add_review(
        self, customer_id: UUID, payload: dict[str, Any]
    ) -> ReviewCustomerDomain:
        booking_id_raw = payload.get("booking_id") or payload.get("bookingId")
        service_id_raw = payload.get("service_id") or payload.get("serviceId")
        rating = float(payload.get("rating") or 5.0)
        comment = (payload.get("comment") or "").strip()

        if rating < 1.0 or rating > 5.0:
            raise ValidationError("Rating must be between 1.0 and 5.0.")
        if not comment:
            raise ValidationError("Review comment is required.")

        booking_id = UUID(str(booking_id_raw)) if booking_id_raw else None
        if booking_id:
            booking = await self.booking_repo.get_by_id(booking_id)
            if not booking:
                raise EntityNotFoundError("Booking", booking_id)
            if booking.customer_id != customer_id:
                raise ValidationError("You can only review bookings you ordered.")
            if booking.status != "completed":
                raise ValidationError("You can only review completed bookings.")

            # Guard against duplicate review for the same booking
            existing = await self.review_repo.get_by_booking_id(booking_id)
            if existing:
                raise EntityConflictError("You have already reviewed this booking.")

            service_id = booking.service_id
        else:
            service_id = UUID(str(service_id_raw)) if service_id_raw else None

        data = {
            "customer_id": customer_id,
            "service_id": service_id,
            "booking_id": booking_id,
            "rating": rating,
            "comment": comment,
        }
        return await self.review_repo.add_review(data)

    async def list_service_reviews(
        self, service_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[ReviewCustomerDomain]:
        return await self.review_repo.list_for_service(service_id, limit=limit, offset=offset)

    async def get_by_booking_id(self, booking_id: UUID) -> ReviewCustomerDomain | None:
        return await self.review_repo.get_by_booking_id(booking_id)
