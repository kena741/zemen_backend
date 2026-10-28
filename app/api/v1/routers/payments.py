"""Payment routes. Writes are 503 unless PAYMENTS_WRITES_ENABLED (default false)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.payments import ChapaVerifyBody, PaymentWriteResult
from app.config import settings
from app.core.security.deps import RequireAuth, RequireProvider
from app.core.security.payments import require_payment_writes
from app.core.services import payment_writes
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.get(
    "/status",
    operation_id="payments_migration_status",
    summary="Payment migration status (writes off until PAYMENTS_WRITES_ENABLED)",
)
async def payments_migration_status() -> dict:
    return {
        "enabled": settings.PAYMENTS_WRITES_ENABLED,
        "phase": 4,
        "chapaConfigured": bool((settings.CHAPA_SECRET_KEY or "").strip()),
        "message": (
            "Money writers exist but stay off until ledger parity and Edge cutover. "
            "USE_BACKEND_PAYMENTS must stay false."
        ),
        "endpoints": [
            "POST /payments/chapa/verify",
            "POST /payments/bookings/{id}/complete",
            "POST /payments/bookings/{id}/refund",
            "POST /wallet/withdrawals",
            "POST /wallet/withdrawals/{id}/cancel",
        ],
        "legacy_edge_functions": [
            "chapa-payment",
            "verify-payment",
            "complete-booking",
            "refund-customer-booking-decline",
            "refund-rejected",
            "verify-provider-activation",
            "verify-service-tier-payment",
            "verify-featured-request-payment",
            "job_request_payment",
        ],
    }


@router.post(
    "/chapa/verify",
    response_model=PaymentWriteResult,
    operation_id="payments_chapa_verify",
    summary="Verify a Chapa tx_ref from env key and apply a purpose-specific write",
)
async def chapa_verify(
    body: ChapaVerifyBody,
    ctx: RequireAuth,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentWriteResult:
    require_payment_writes()
    result = await payment_writes.verify_and_apply(
        db,
        ctx=ctx,
        tx_ref=body.tx_ref,
        purpose=body.purpose,
        booking_id=body.booking_id,
    )
    return PaymentWriteResult.model_validate(result)


@router.post(
    "/bookings/{booking_id}/complete",
    response_model=PaymentWriteResult,
    operation_id="payments_complete_booking",
    summary="Provider completion payout (commission from booking / app_settings)",
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
    operation_id="payments_refund_booking",
    summary="Cancel/decline refund. Rejects completed bookings. Amount from payments/booking.",
)
async def refund_booking(
    booking_id: UUID,
    ctx: RequireAuth,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentWriteResult:
    require_payment_writes()
    result = await payment_writes.refund_booking(db, ctx=ctx, booking_id=booking_id)
    return PaymentWriteResult.model_validate(result)
