"""Payment routes for Chapa gateway, provider activation, tier upgrades, and taxes."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.payments import (
    ActivationVerifyRequest,
    BankOut,
    ChapaVerifyBody,
    CountryTaxOut,
    FeaturedPaymentVerifyRequest,
    PaymentSettingsOut,
    PaymentWriteResult,
    TierPaymentVerifyRequest,
)
from app.config import settings
from app.core.security.deps import RequireAuth, RequireProvider
from app.core.security.payments import require_payment_writes
from app.core.services import payment_writes
from app.core.services.chapa_payment_service import ChapaPaymentService
from app.persistence.repositories.app_settings_repo import AppSettingsRepository
from app.persistence.repositories.provider_repo import ProviderRepository
from app.persistence.repositories.service_repo import ServiceRepository
from app.persistence.repositories.tax_repo import CountryTaxRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/payments", tags=["Payments"])


def get_chapa_payment_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChapaPaymentService:
    return ChapaPaymentService(
        app_settings_repo=AppSettingsRepository(db),
        tax_repo=CountryTaxRepository(db),
        provider_repo=ProviderRepository(db),
        service_repo=ServiceRepository(db),
    )


# ======================== Discovery & Gateway Configuration ========================


@router.get(
    "/settings",
    response_model=PaymentSettingsOut,
    summary="Get mobile payment gateway settings and public keys",
)
async def get_payment_settings(
    service: Annotated[ChapaPaymentService, Depends(get_chapa_payment_service)],
) -> PaymentSettingsOut:
    cfg = await service.get_payment_settings()
    return PaymentSettingsOut.model_validate(cfg)


@router.get(
    "/taxes",
    response_model=list[CountryTaxOut],
    summary="List active platform taxes and charges",
)
async def list_taxes(
    service: Annotated[ChapaPaymentService, Depends(get_chapa_payment_service)],
) -> list[CountryTaxOut]:
    taxes = await service.list_taxes()
    return [CountryTaxOut.model_validate(t) for t in taxes]


@router.get(
    "/chapa/banks",
    response_model=list[BankOut],
    summary="List Ethiopian banks supported by Chapa for payouts and transfers",
)
async def list_chapa_banks(
    service: Annotated[ChapaPaymentService, Depends(get_chapa_payment_service)],
) -> list[BankOut]:
    banks = await service.list_supported_banks()
    return [BankOut.model_validate(b) for b in banks]


# ======================== Chapa Verification Endpoints ========================


@router.post(
    "/chapa/verify",
    summary="Verify general Chapa payment transaction",
)
async def chapa_verify(
    body: ChapaVerifyBody,
    service: Annotated[ChapaPaymentService, Depends(get_chapa_payment_service)],
) -> dict[str, Any]:
    return await service.verify_chapa_tx(tx_ref=body.tx_ref)


@router.post(
    "/provider-activation/verify",
    summary="Verify provider onboarding activation fee payment",
)
async def verify_provider_activation(
    body: ActivationVerifyRequest,
    service: Annotated[ChapaPaymentService, Depends(get_chapa_payment_service)],
) -> dict[str, Any]:
    return await service.verify_provider_activation(
        tx_ref=body.tx_ref,
        provider_id=body.provider_id,
        amount=body.amount,
    )


@router.post(
    "/service-tier/verify",
    summary="Verify provider service tier upgrade payment",
)
async def verify_service_tier_payment(
    body: TierPaymentVerifyRequest,
    service: Annotated[ChapaPaymentService, Depends(get_chapa_payment_service)],
) -> dict[str, Any]:
    return await service.verify_service_tier_payment(
        tx_ref=body.tx_ref,
        provider_id=body.provider_id,
        amount=body.amount,
        target_tier=body.tier_max,
    )


@router.post(
    "/featured-request/verify",
    summary="Verify service featured placement payment",
)
async def verify_featured_request_payment(
    body: FeaturedPaymentVerifyRequest,
    service: Annotated[ChapaPaymentService, Depends(get_chapa_payment_service)],
) -> dict[str, Any]:
    return await service.verify_featured_request_payment(
        tx_ref=body.tx_ref,
        provider_id=body.provider_id,
        service_id=body.service_id,
        amount=body.amount,
    )


# ======================== Legacy / Admin Payout Endpoints ========================


@router.get(
    "/status",
    summary="Payment migration status",
)
async def payments_migration_status() -> dict[str, Any]:
    return {
        "enabled": settings.PAYMENTS_WRITES_ENABLED,
        "phase": 6,
        "chapaConfigured": bool((settings.CHAPA_SECRET_KEY or "").strip()),
    }


@router.post(
    "/bookings/{booking_id}/complete",
    response_model=PaymentWriteResult,
    summary="Provider completion payout",
)
async def complete_booking(
    booking_id: UUID,
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentWriteResult:
    require_payment_writes()
    result = await payment_writes.complete_booking_payout(db, ctx=ctx, booking_id=booking_id)
    return PaymentWriteResult.model_validate(result)


@router.post(
    "/bookings/{booking_id}/refund",
    response_model=PaymentWriteResult,
    summary="Cancel/decline refund",
)
async def refund_booking(
    booking_id: UUID,
    ctx: RequireAuth,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentWriteResult:
    require_payment_writes()
    result = await payment_writes.refund_booking(db, ctx=ctx, booking_id=booking_id)
    return PaymentWriteResult.model_validate(result)
