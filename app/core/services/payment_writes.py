"""Gated money writers. Routers must refuse unless PAYMENTS_WRITES_ENABLED.

Never trust amount, user id, or role from the client for credits/debits.
Chapa amount and booking columns are the source of truth.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.deps import AuthContext
from app.core.services import booking_service, chapa_client, commission, ledger
from app.core.services.chapa_client import ChapaHttp
from app.persistence.sqlalchemy.models import (
    BookedService,
    Customer,
    Payment,
    Provider,
    ProviderPaymentMethod,
    WithdrawalHistory,
)

REFUNDABLE = frozenset({"pending", "accepted", "rejected"})
COMPLETABLE = frozenset({"accepted", "on_the_way", "in_progress", "hold", "pending_approval", "pending_extra_payment"})


def _owns_customer(booking: BookedService, ctx: AuthContext) -> bool:
    return booking.customer_id == ctx.customer_id or booking.customer_user_id == ctx.user_id


def _owns_provider(booking: BookedService, ctx: AuthContext) -> bool:
    return ctx.provider_id is not None and booking.provider_id == ctx.provider_id


def _short(booking_id: UUID) -> str:
    return str(booking_id).replace("-", "")[:6]


def refund_note(booking_id: UUID) -> str:
    return f"Order #{_short(booking_id)} cancel refund"


def payout_note(booking_id: UUID) -> str:
    return f"Order #{_short(booking_id)} completed (payout after admin commission)"


async def _payment_for_ref(db: AsyncSession, tx_ref: str) -> Payment | None:
    return (
        await db.execute(select(Payment).where(Payment.provider_ref == tx_ref).limit(1))
    ).scalar_one_or_none()


async def verify_and_apply(
    db: AsyncSession,
    *,
    ctx: AuthContext,
    tx_ref: str,
    purpose: str,
    booking_id: UUID | None = None,
    http: ChapaHttp | None = None,
) -> dict:
    purpose = (purpose or "").strip().lower()
    if purpose not in {"wallet", "booking", "activation", "tier", "featured", "job"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid purpose")
    chapa = await chapa_client.verify_tx_ref(tx_ref, http=http)
    existing_pay = await _payment_for_ref(db, chapa.tx_ref)

    if purpose == "wallet":
        if existing_pay is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="tx_ref already used")
        if ctx.customer_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Customer profile required")
        customer = (
            await db.execute(select(Customer).where(Customer.id == ctx.customer_id))
        ).scalar_one_or_none()
        if customer is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
        row, created = await ledger.apply_ledger(
            db,
            kind="customer",
            owner_id=customer.id,
            user_id=customer.user_id or ctx.user_id,
            amount=chapa.amount,
            is_credit=True,
            note="Wallet top-up",
            transaction_id=chapa.tx_ref,
            payment_type="chapa",
        )
        return {
            "purpose": purpose,
            "tx_ref": chapa.tx_ref,
            "amount": str(chapa.amount),
            "created": created,
            "id": str(row.id),
        }

    if purpose == "booking":
        if booking_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bookingId is required")
        booking = await booking_service.get_booking(db, booking_id)
        if booking is None or not _owns_customer(booking, ctx):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
        expected = commission.booking_gross(booking)
        if expected > 0 and chapa.amount + Decimal("0.01") < expected:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Paid amount is less than booking total")
        if existing_pay is not None and existing_pay.booking_id != booking.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="tx_ref already used")
        booking.payment_completed = True
        booking.payment_status = "payment_completed"
        booking.payment_type = booking.payment_type or "chapa"
        booking.next_cycle_due = False
        if existing_pay is None:
            db.add(
                Payment(
                    id=uuid4(),
                    booking_id=booking.id,
                    customer_id=booking.customer_id or ctx.customer_id or ctx.user_id,
                    amount=chapa.amount,
                    currency=chapa.currency,
                    status="payment_completed",
                    payment_method="chapa",
                    provider="chapa",
                    provider_ref=chapa.tx_ref,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
        await db.flush()
        return {
            "purpose": purpose,
            "tx_ref": chapa.tx_ref,
            "booking_id": str(booking.id),
            "amount": str(chapa.amount),
        }

    if purpose == "activation":
        if ctx.provider_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Provider profile required")
        provider = (
            await db.execute(select(Provider).where(Provider.id == ctx.provider_id).with_for_update())
        ).scalar_one_or_none()
        if provider is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
        if provider.activation_tx_ref and provider.activation_tx_ref != chapa.tx_ref:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Activation already paid")
        provider.activation_paid = True
        provider.activation_paid_at = provider.activation_paid_at or datetime.now(UTC)
        provider.activation_tx_ref = chapa.tx_ref
        await db.flush()
        return {"purpose": purpose, "tx_ref": chapa.tx_ref, "provider_id": str(provider.id)}

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"{purpose} verification is scaffolded; Edge remains the writer",
    )


async def complete_booking_payout(db: AsyncSession, *, ctx: AuthContext, booking_id: UUID) -> dict:
    booking = await booking_service.get_booking(db, booking_id)
    if booking is None or not _owns_provider(booking, ctx):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    current = (booking.status or "").lower()
    note = payout_note(booking.id)
    existing = await ledger.find_existing(
        db, transaction_id=str(booking.id), kind="provider", note=note, is_credit=True
    )
    if current == "completed" and existing is not None:
        return {"booking_id": str(booking.id), "status": "completed", "created": False, "amount": existing.amount}
    if current not in COMPLETABLE and current != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot complete booking in status '{booking.status}'",
        )
    gross = commission.booking_gross(booking)
    rule = await commission.admin_commission_rule(db)
    payout = commission.provider_net(gross, booking_commission=booking.admin_commission, rule=rule)
    if payout <= 0:
        booking.status = "completed"
        await db.flush()
        return {"booking_id": str(booking.id), "status": "completed", "created": False, "amount": "0"}
    row, created = await ledger.apply_ledger(
        db,
        kind="provider",
        owner_id=booking.provider_id,
        user_id=booking.provider_user_id,
        amount=payout,
        is_credit=True,
        note=note,
        transaction_id=str(booking.id),
        payment_type=booking.payment_type or "wallet",
    )
    booking.status = "completed"
    await db.flush()
    return {"booking_id": str(booking.id), "status": "completed", "created": created, "amount": row.amount}


async def refund_booking(db: AsyncSession, *, ctx: AuthContext, booking_id: UUID) -> dict:
    booking = await booking_service.get_booking(db, booking_id)
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if not (_owns_customer(booking, ctx) or _owns_provider(booking, ctx)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    current = (booking.status or "").lower()
    if current not in REFUNDABLE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot refund booking in status '{booking.status}'",
        )
    if booking.payment_completed is not True:
        return {"booking_id": str(booking.id), "created": False, "amount": "0", "reason": "unpaid"}
    customer_id = booking.customer_id
    if customer_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Booking has no customer")
    pay = (
        await db.execute(
            select(Payment)
            .where(Payment.booking_id == booking.id, Payment.status == "payment_completed")
            .order_by(Payment.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    amount = Decimal(pay.amount) if pay is not None and pay.amount else commission.booking_gross(booking)
    if amount <= 0:
        return {"booking_id": str(booking.id), "created": False, "amount": "0", "reason": "zero"}
    note = refund_note(booking.id)
    row, created = await ledger.apply_ledger(
        db,
        kind="customer",
        owner_id=customer_id,
        user_id=booking.customer_user_id,
        amount=amount,
        is_credit=True,
        note=note,
        transaction_id=str(booking.id),
        payment_type=booking.payment_type or "chapa",
    )
    return {"booking_id": str(booking.id), "created": created, "amount": row.amount}


async def request_withdrawal(
    db: AsyncSession,
    *,
    ctx: AuthContext,
    amount: Decimal,
    payment_method_id: UUID | None,
    note: str | None,
) -> WithdrawalHistory:
    if ctx.provider_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Provider profile required")
    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be greater than 0")
    provider = (
        await db.execute(select(Provider).where(Provider.id == ctx.provider_id).with_for_update())
    ).scalar_one_or_none()
    if provider is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    balance = ledger.parse_money(provider.wallet_amount)
    if amount > balance:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Amount exceeds wallet balance")
    method = None
    if payment_method_id is not None:
        method = (
            await db.execute(
                select(ProviderPaymentMethod).where(
                    ProviderPaymentMethod.id == payment_method_id,
                    ProviderPaymentMethod.provider_id == ctx.provider_id,
                )
            )
        ).scalar_one_or_none()
        if method is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment method not found")
    now = datetime.now(UTC)
    row = WithdrawalHistory(
        id=uuid4(),
        amount=ledger.format_provider_wallet(amount),
        created_date=now,
        note=note,
        payment_status="pending",
        provider_id=ctx.provider_id,
        payment_method_id=str(payment_method_id) if payment_method_id else None,
        holder_name=method.holder_name if method else None,
        bank_name=method.bank_name if method else None,
        account_number=method.account_number if method else None,
        swift_code=method.swift_code if method else None,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def cancel_pending_withdrawal(db: AsyncSession, *, ctx: AuthContext, withdrawal_id: UUID) -> WithdrawalHistory:
    if ctx.provider_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Provider profile required")
    row = (
        await db.execute(
            select(WithdrawalHistory).where(
                WithdrawalHistory.id == withdrawal_id,
                WithdrawalHistory.provider_id == ctx.provider_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Withdrawal not found")
    if (row.payment_status or "").lower() not in {"pending"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending withdrawals can be cancelled")
    row.payment_status = "cancelled"
    await db.flush()
    await db.refresh(row)
    return row
