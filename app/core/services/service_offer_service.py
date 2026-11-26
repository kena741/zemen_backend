"""Service for Custom Service Offers, negotiation, and acceptance-to-booking transitions."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.domain.booking import BookingDomain
from app.domain.exceptions import (
    EntityConflictError,
    EntityNotFoundError,
    PermissionDeniedError,
    StateTransitionError,
    ValidationError,
)
from app.domain.offer import ServiceOfferDomain
from app.persistence.repositories.mobile_booking_repo import MobileBookingRepository
from app.persistence.repositories.service_offer_repo import ServiceOfferRepository
from app.persistence.repositories.service_repo import ServiceRepository


class ServiceOfferService:
    def __init__(
        self,
        offer_repo: ServiceOfferRepository,
        service_repo: ServiceRepository,
        booking_repo: MobileBookingRepository,
    ) -> None:
        self.offer_repo = offer_repo
        self.service_repo = service_repo
        self.booking_repo = booking_repo

    async def create_offer(
        self,
        customer_id: UUID,
        payload: dict[str, Any],
    ) -> ServiceOfferDomain:
        service_id_raw = payload.get("service_id")
        provider_id_raw = payload.get("provider_id")
        offered_price = float(payload.get("offered_price") or 0.0)
        service_desc = (payload.get("service_description") or "").strip()
        booking_address = payload.get("booking_address")

        if offered_price <= 0:
            raise ValidationError("offered_price must be greater than 0.")
        if not service_desc:
            raise ValidationError("service_description is required for a custom offer.")
        if not booking_address:
            raise ValidationError("booking_address is required for a custom offer.")

        if not service_id_raw or not provider_id_raw:
            raise ValidationError("service_id and provider_id are required.")

        s_uuid = UUID(str(service_id_raw))
        service = await self.service_repo.get_by_id(s_uuid)
        if not service:
            raise EntityNotFoundError("Service", s_uuid)
        if not service.allows_custom_offer:
            raise ValidationError("This service does not allow custom pricing offers.")

        # Guard against duplicate pending offers
        c_str = str(customer_id)
        p_str = str(provider_id_raw)
        s_str = str(service_id_raw)
        if await self.offer_repo.has_pending_offer(s_str, c_str, p_str):
            raise EntityConflictError(
                "You already have a pending offer for this service. Please wait for provider response."
            )

        data = {
            "id": uuid4(),
            "service_id": s_str,
            "customer_id": c_str,
            "provider_id": p_str,
            "offered_price": offered_price,
            "message": payload.get("message"),
            "booking_date": payload.get("booking_date"),
            "booking_address": booking_address,
            "service_description": service_desc,
            "status": "pending",
        }
        return await self.offer_repo.create_offer(data)

    async def get_offer(
        self,
        offer_id: UUID,
        actor_id: UUID,
        actor_role: str,
    ) -> ServiceOfferDomain:
        offer = await self.offer_repo.get_by_id_enriched(offer_id)
        if not offer:
            raise EntityNotFoundError("ServiceOffer", offer_id)

        act_str = str(actor_id)
        if actor_role == "customer" and offer.customer_id != act_str:
            raise PermissionDeniedError("You do not own this offer.")
        if actor_role == "provider" and offer.provider_id != act_str:
            raise PermissionDeniedError("You do not own this offer.")

        return offer

    async def get_by_booking_id(self, booking_id: str) -> ServiceOfferDomain:
        offer = await self.offer_repo.get_by_booking_id(booking_id)
        if not offer:
            raise EntityNotFoundError("ServiceOffer for booking", booking_id)
        return offer

    async def list_customer_offers(
        self, customer_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[ServiceOfferDomain]:
        return await self.offer_repo.list_for_customer(str(customer_id), limit=limit, offset=offset)

    async def list_provider_offers(
        self, provider_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[ServiceOfferDomain]:
        return await self.offer_repo.list_for_provider(str(provider_id), limit=limit, offset=offset)

    async def cancel_offer(self, offer_id: UUID, customer_id: UUID) -> ServiceOfferDomain:
        offer = await self.offer_repo.get_by_id(offer_id)
        if not offer:
            raise EntityNotFoundError("ServiceOffer", offer_id)
        if offer.customer_id != str(customer_id):
            raise PermissionDeniedError("You do not own this offer.")
        if offer.status != "pending":
            raise StateTransitionError(
                offer.status,
                "cancelled",
                "Only pending offers can be cancelled.",
            )

        updated = await self.offer_repo.update_status(offer_id, "cancelled")
        if not updated:
            raise EntityNotFoundError("ServiceOffer", offer_id)
        return updated

    async def reject_offer(self, offer_id: UUID, provider_id: UUID) -> ServiceOfferDomain:
        offer = await self.offer_repo.get_by_id(offer_id)
        if not offer:
            raise EntityNotFoundError("ServiceOffer", offer_id)
        if offer.provider_id != str(provider_id):
            raise PermissionDeniedError("You do not own this offer.")
        if offer.status != "pending":
            raise StateTransitionError(
                offer.status,
                "rejected",
                "Only pending offers can be rejected.",
            )

        updated = await self.offer_repo.update_status(offer_id, "rejected")
        if not updated:
            raise EntityNotFoundError("ServiceOffer", offer_id)
        return updated

    async def accept_and_book(
        self, offer_id: UUID, provider_id: UUID
    ) -> BookingDomain:
        offer = await self.offer_repo.get_by_id(offer_id)
        if not offer:
            raise EntityNotFoundError("ServiceOffer", offer_id)
        if offer.provider_id != str(provider_id):
            raise PermissionDeniedError("You do not own this offer.")

        # If already linked to booking, return that booking
        if offer.booking_id:
            booking = await self.booking_repo.get_by_id(UUID(offer.booking_id))
            if booking:
                return booking

        if offer.status not in {"pending", "accepted"}:
            raise StateTransitionError(
                offer.status,
                "accepted",
                "Offer cannot be accepted in its current state.",
            )

        # 1. Create booking in booked_service
        now = datetime.now(timezone.utc)
        booking_data = {
            "id": uuid4(),
            "provider_id": UUID(offer.provider_id),
            "customer_id": UUID(offer.customer_id),
            "service_id": UUID(offer.service_id) if offer.service_id else None,
            "service_name": offer.service_description or "Custom Service Offer",
            "price": offer.offered_price,
            "total_amount": offer.offered_price,
            "sub_total": offer.offered_price,
            "booking_date": offer.booking_date or now,
            "booking_address": offer.booking_address,
            "status": "accepted",
            "payment_status": "pending_payment",
            "payment_completed": False,
        }
        new_booking = await self.booking_repo.upsert_booking(booking_data)

        # 2. Update offer status and link booking_id
        await self.offer_repo.update_status(offer_id, "accepted")
        await self.offer_repo.attach_booking(offer_id, str(new_booking.id))

        return new_booking

    async def attach_booking(
        self, offer_id: UUID, booking_id: str, actor_id: UUID
    ) -> ServiceOfferDomain:
        offer = await self.offer_repo.get_by_id(offer_id)
        if not offer:
            raise EntityNotFoundError("ServiceOffer", offer_id)

        act_str = str(actor_id)
        if offer.customer_id != act_str and offer.provider_id != act_str:
            raise PermissionDeniedError("You do not have access to this offer.")

        updated = await self.offer_repo.attach_booking(offer_id, booking_id)
        if not updated:
            raise EntityNotFoundError("ServiceOffer", offer_id)
        return updated

