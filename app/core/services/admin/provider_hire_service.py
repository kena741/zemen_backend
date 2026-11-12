"""Service for Provider Service/Hire History and Past Hires."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.core.security.admin_deps import AdminContext
from app.core.services.admin.audit_service import AdminAuditService
from app.domain.provider import (
    ProviderBookingHistoryItemDomain,
    RepeatCustomerDomain,
    ServiceHistoryStatsDomain,
)
from app.persistence.repositories.provider_booking_repo import ProviderBookingRepository
from app.persistence.repositories.provider_repo import ProviderRepository


class ProviderHireAdminService:
    def __init__(
        self,
        booking_repo: ProviderBookingRepository,
        provider_repo: ProviderRepository,
        audit_service: AdminAuditService,
    ) -> None:
        self.booking_repo = booking_repo
        self.provider_repo = provider_repo
        self.audit_service = audit_service

    async def list_hire_history(
        self, provider_id: UUID
    ) -> tuple[
        list[ProviderBookingHistoryItemDomain],
        ServiceHistoryStatsDomain,
        list[RepeatCustomerDomain],
    ]:
        provider = await self.provider_repo.get_by_id(provider_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
        return await self.booking_repo.list_for_provider(provider_id)

    async def log_past_hire(
        self,
        provider_id: UUID,
        booking_date: datetime,
        amount: float,
        customer_id: UUID | None = None,
        service_id: UUID | None = None,
        note: str | None = None,
        admin_note: str | None = None,
        ctx: AdminContext | None = None,
    ) -> dict[str, Any]:
        provider = await self.provider_repo.get_by_id(provider_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

        # Booking date must be in the past
        now = datetime.now(timezone.utc)
        if booking_date > now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Past hire booking date must be in the past",
            )

        booking = await self.booking_repo.log_past_hire(
            provider_id=provider_id,
            customer_id=customer_id,
            service_id=service_id,
            booking_date=booking_date,
            amount=amount,
            note=note,
            admin_note=admin_note,
        )

        await self.audit_service.log_action(
            action="create",
            resource_type="provider.past_hire",
            resource_id=str(booking.id),
            summary=f"Logged past hire of {amount} ETB for provider {provider.full_name}",
            ctx=ctx,
        )

        return {"id": str(booking.id), "amount": amount}

    async def update_hire_followup_note(
        self,
        provider_id: UUID,
        booking_id: UUID,
        admin_note: str | None,
        ctx: AdminContext | None = None,
    ) -> dict[str, Any]:
        provider = await self.provider_repo.get_by_id(provider_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

        updated = await self.booking_repo.update_hire_note(
            provider_id=provider_id,
            booking_id=booking_id,
            admin_note=admin_note,
        )
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found for this provider",
            )

        await self.audit_service.log_action(
            action="update",
            resource_type="provider.hire_history.follow_up",
            resource_id=str(booking_id),
            summary=f"Updated hire follow-up note for provider {provider.full_name}",
            ctx=ctx,
        )

        return {"id": str(booking_id), "followUp": admin_note or ""}
