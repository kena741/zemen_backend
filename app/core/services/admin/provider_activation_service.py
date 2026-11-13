"""Service for Provider Activation Payments (manual & Chapa)."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.core.security.admin_deps import AdminContext
from app.core.services.admin.audit_service import AdminAuditService
from app.persistence.repositories.provider_repo import ProviderRepository


class ProviderActivationAdminService:
    def __init__(
        self,
        provider_repo: ProviderRepository,
        audit_service: AdminAuditService,
    ) -> None:
        self.provider_repo = provider_repo
        self.audit_service = audit_service

    async def initiate_activation(
        self,
        provider_id: UUID,
        mode: str,
        fee_amount: float,
        tx_ref: str | None = None,
        note: str | None = None,
        ctx: AdminContext | None = None,
    ) -> dict[str, Any]:
        provider = await self.provider_repo.get_by_id(provider_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

        if provider.activation_paid:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Provider activation has already been paid",
            )

        now = datetime.now(timezone.utc)
        ref = tx_ref or f"act-{provider_id.hex[:8]}-{secrets.token_hex(4)}"

        if mode == "manual":
            values = {
                "activation_paid": True,
                "activation_paid_at": now,
                "activation_tx_ref": ref,
                "service_tier_max": max(1, provider.service_tier_max),
                "active": True,
                "updated_at": now,
            }
            await self.provider_repo.update(provider_id, values)

            await self.audit_service.log_action(
                action="activate_manual",
                resource_type="provider",
                resource_id=str(provider_id),
                summary=f"Manually marked activation paid ({fee_amount} ETB) for provider {provider.full_name}",
                metadata={"fee_amount": fee_amount, "tx_ref": ref, "note": note},
                ctx=ctx,
            )

            return {
                "status": "success",
                "mode": "manual",
                "provider_id": str(provider_id),
                "provider_name": provider.full_name,
                "activation_paid_at": now.isoformat(),
                "tx_ref": ref,
                "fee_amount": fee_amount,
                "note": note,
            }

        # Chapa checkout mode
        await self.provider_repo.update(provider_id, {"activation_tx_ref": ref, "updated_at": now})

        checkout_url = f"https://checkout.chapa.co/checkout/payment/{ref}"
        return {
            "status": "pending",
            "mode": "chapa",
            "checkout_url": checkout_url,
            "provider_id": str(provider_id),
            "provider_name": provider.full_name,
            "tx_ref": ref,
            "fee_amount": fee_amount,
            "note": note,
        }

    async def verify_activation(
        self,
        provider_id: UUID,
        ctx: AdminContext | None = None,
    ) -> dict[str, Any]:
        provider = await self.provider_repo.get_by_id(provider_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

        if provider.activation_paid:
            return {
                "status": "already_paid",
                "already_paid": True,
                "provider_id": str(provider_id),
                "activation_paid_at": provider.activation_paid_at.isoformat() if provider.activation_paid_at else None,
            }

        now = datetime.now(timezone.utc)
        await self.provider_repo.update(
            provider_id,
            {
                "activation_paid": True,
                "activation_paid_at": now,
                "service_tier_max": max(1, provider.service_tier_max),
                "active": True,
                "updated_at": now,
            },
        )

        await self.audit_service.log_action(
            action="verify_activation",
            resource_type="provider",
            resource_id=str(provider_id),
            summary=f"Verified activation payment for provider {provider.full_name}",
            ctx=ctx,
        )

        return {
            "status": "success",
            "chapa_status": "success",
            "message": "Activation verified successfully",
            "provider_id": str(provider_id),
            "activation_paid_at": now.isoformat(),
        }

    async def reconcile_activation(
        self,
        provider_id: UUID,
        tx_ref: str | None = None,
        fee_amount: float | None = None,
        note: str | None = None,
        ctx: AdminContext | None = None,
    ) -> dict[str, Any]:
        provider = await self.provider_repo.get_by_id(provider_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

        now = datetime.now(timezone.utc)
        ref = tx_ref or provider.activation_tx_ref or f"reconcile-{secrets.token_hex(4)}"

        await self.provider_repo.update(
            provider_id,
            {
                "activation_paid": True,
                "activation_paid_at": now,
                "activation_tx_ref": ref,
                "service_tier_max": max(1, provider.service_tier_max),
                "active": True,
                "updated_at": now,
            },
        )

        await self.audit_service.log_action(
            action="reconcile_activation",
            resource_type="provider",
            resource_id=str(provider_id),
            summary=f"Reconciled activation for provider {provider.full_name}",
            metadata={"tx_ref": ref, "fee_amount": fee_amount, "note": note},
            ctx=ctx,
        )

        return {
            "status": "reconciled",
            "provider_id": str(provider_id),
            "tx_ref": ref,
            "activation_paid_at": now.isoformat(),
        }

