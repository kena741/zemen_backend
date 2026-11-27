"""Payment routes for Chapa gateway, provider activation, tier upgrades, and taxes."""

from __future__ import annotations

import hashlib
import hmac
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.payments import (
    ActivationVerifyRequest,
    BankOut,
    ChapaInitializeRequest,
    ChapaInitializeResponse,
    ChapaVerifyBody,
    CountryTaxOut,
    FeaturedPaymentVerifyRequest,
    PaymentSettingsOut,
    PaymentWriteResult,
    SubscriptionPlanOut,
    TierPaymentVerifyRequest,
    TierPurchaseInitiateRequest,
)
from app.config import settings
from app.core.security.deps import RequireAuth, RequireProvider
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
    "/plans",
    response_model=list[SubscriptionPlanOut],
    summary="List available provider subscription plans",
)
async def list_subscription_plans(
    service: Annotated[ChapaPaymentService, Depends(get_chapa_payment_service)],
) -> list[SubscriptionPlanOut]:
    plans = await service.list_subscription_plans()
    return [SubscriptionPlanOut.model_validate(p) for p in plans]


@router.get(
    "/chapa/banks",
    response_model=list[BankOut],
    summary="List Ethiopian banks supported by Chapa for payouts and transfers",
)
async def list_chapa_banks(
    service: Annotated[ChapaPaymentService, Depends(get_chapa_payment_service)],
    refresh: bool = Query(
        default=False,
        description="Force refresh the cached banks list from Chapa API",
    ),
) -> list[BankOut]:
    banks = await service.list_supported_banks(force_refresh=refresh)
    return [BankOut.model_validate(b) for b in banks]


# ======================== Chapa Checkout & Verification Endpoints ========================


@router.post(
    "/chapa/initialize",
    response_model=ChapaInitializeResponse,
    summary="Initialize hosted checkout session with Chapa API",
)
async def initialize_chapa_payment(
    body: ChapaInitializeRequest,
    service: Annotated[ChapaPaymentService, Depends(get_chapa_payment_service)],
) -> ChapaInitializeResponse:
    res = await service.initialize_payment(
        amount=body.amount,
        currency=body.currency,
        email=body.email,
        first_name=body.first_name,
        last_name=body.last_name,
        tx_ref=body.tx_ref,
        phone_number=body.phone_number,
        callback_url=body.callback_url,
        return_url=body.return_url,
    )
    return ChapaInitializeResponse.model_validate(res)


@router.post(
    "/service-tier/initiate",
    response_model=ChapaInitializeResponse,
    summary="Initiate provider service tier upgrade checkout session",
)
async def initiate_service_tier_purchase(
    body: TierPurchaseInitiateRequest,
    ctx: RequireProvider,
    service: Annotated[ChapaPaymentService, Depends(get_chapa_payment_service)],
) -> ChapaInitializeResponse:
    res = await service.initiate_tier_purchase(
        provider_id=ctx.provider_id,
        plan_id=body.plan_id,
        tier_max=body.tier_max,
        callback_url=body.callback_url,
        return_url=body.return_url,
    )
    return ChapaInitializeResponse.model_validate(res)


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
    request: Request,
    service: Annotated[ChapaPaymentService, Depends(get_chapa_payment_service)],
) -> dict[str, Any]:
    skip = bool(body.skip_gateway_verify)
    if skip:
        secret = (settings.PAYMENT_CONFIRM_SECRET or "").strip()
        provided = (request.headers.get("x-zemen-pay-sig") or "").strip()
        if not secret or not provided:
            raise HTTPException(
                status_code=403, detail="Payment confirm signature required"
            )
        tier = "" if body.tier_max is None else str(body.tier_max)
        amt = "" if body.amount is None else f"{float(body.amount):.2f}"
        payload = f"{body.tx_ref}:{body.provider_id}:{tier}:{amt}"
        expected = hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(provided, expected):
            raise HTTPException(
                status_code=403, detail="Invalid payment confirm signature"
            )

    return await service.verify_service_tier_payment(
        tx_ref=body.tx_ref,
        provider_id=body.provider_id,
        amount=body.amount,
        target_tier=body.tier_max,
        skip_gateway_verify=skip,
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
    result = await payment_writes.refund_booking(db, ctx=ctx, booking_id=booking_id)
    return PaymentWriteResult.model_validate(result)
