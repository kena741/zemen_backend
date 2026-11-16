"""Service for mobile booking orchestration, setOrder upserts, queries, and permissions."""

from __future__ import annotations

import random
from typing import Any
from uuid import UUID, uuid4

from app.domain.booking import BookingDomain, MonthlyEarningsDomain
from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.persistence.repositories.customer_repo import CustomerRepository
from app.persistence.repositories.mobile_booking_repo import MobileBookingRepository
from app.persistence.repositories.provider_repo import ProviderRepository


class MobileBookingService:
    def __init__(
        self,
        booking_repo: MobileBookingRepository,
        customer_repo: CustomerRepository,
        provider_repo: ProviderRepository,
    ) -> None:
        self.booking_repo = booking_repo
        self.customer_repo = customer_repo
        self.provider_repo = provider_repo

    async def create_or_update_booking(
        self,
        actor_user_id: UUID,
        actor_role: str,
        payload: dict[str, Any],
        actor_customer_id: UUID | None = None,
        actor_provider_id: UUID | None = None,
    ) -> BookingDomain:
        data = dict(payload)

        # Generate OTP if missing
        if not data.get("otp"):
            data["otp"] = f"{random.randint(100000, 999999)}"

        # Resolve customer details if caller is customer
        if actor_role == "customer" or actor_customer_id:
            cust_id = actor_customer_id
            if not cust_id:
                cust = await self.customer_repo.get_by_user_id(actor_user_id)
                if cust:
                    cust_id = cust.id
            if cust_id:
                data["customer_id"] = cust_id
                data["customer_user_id"] = actor_user_id

        # Resolve provider details if caller is provider
        elif actor_role == "provider" or actor_provider_id:
            prov_id = actor_provider_id
            if not prov_id:
                prov = await self.provider_repo.get_by_user_id(actor_user_id)
                if prov:
                    prov_id = prov.id
            if prov_id:
                data["provider_id"] = prov_id
                data["provider_user_id"] = actor_user_id

        if not data.get("provider_id"):
            raise ValidationError("provider_id is required to create a booking.")

        return await self.booking_repo.upsert_booking(data)

    async def get_booking(
        self,
        booking_id: UUID,
        actor_user_id: UUID,
        actor_role: str,
        customer_id: UUID | None = None,
        provider_id: UUID | None = None,
    ) -> BookingDomain:
        booking = await self.booking_repo.get_by_id_enriched(booking_id)
        if not booking:
            raise EntityNotFoundError("Booking", booking_id)

        # Check actor visibility
        if actor_role == "admin":
            return booking
        if customer_id and booking.customer_id == customer_id:
            return booking
        if provider_id and booking.provider_id == provider_id:
            return booking
        if booking.customer_user_id == actor_user_id or booking.provider_user_id == actor_user_id:
            return booking

        raise PermissionDeniedError("You do not have access to this booking.")

    async def list_customer_bookings(
        self,
        customer_id: UUID,
        status: str | None = None,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BookingDomain]:
        return await self.booking_repo.list_for_customer(
            customer_id=customer_id,
            status=status,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )

    async def list_provider_bookings(
        self,
        provider_id: UUID,
        status: str | None = None,
        is_upcoming: bool = False,
        is_completed: bool = False,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BookingDomain]:
        return await self.booking_repo.list_for_provider(
            provider_id=provider_id,
            status=status,
            is_upcoming=is_upcoming,
            is_completed=is_completed,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )

    async def get_provider_monthly_earnings(
        self, provider_id: UUID, year: int | None = None
    ) -> list[MonthlyEarningsDomain]:
        return await self.booking_repo.get_monthly_earnings(provider_id=provider_id, year=year)

    async def delete_unpaid_pending(self, booking_id: UUID, customer_id: UUID) -> bool:
        deleted = await self.booking_repo.delete_unpaid_pending(booking_id, customer_id)
        if not deleted:
            raise EntityNotFoundError("Unpaid pending booking", booking_id)
        return True

