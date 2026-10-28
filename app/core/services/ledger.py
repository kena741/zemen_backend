"""Single money-movement primitive. Ledger + balance in one flush.

Idempotent on (transactionId, type, note, isCredit). Existing duplicate groups
in production block a unique index — this check runs after FOR UPDATE.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import Customer, Provider, WalletTransaction


def parse_money(value: object) -> Decimal:
    try:
        amount = Decimal(str(value if value is not None else "0").strip() or "0")
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid amount") from exc
    return amount


def format_provider_wallet(amount: Decimal) -> str:
    quantized = amount.quantize(Decimal("0.01"))
    return format(quantized, "f")


async def find_existing(
    db: AsyncSession,
    *,
    transaction_id: str,
    kind: str,
    note: str,
    is_credit: bool,
) -> WalletTransaction | None:
    return (
        await db.execute(
            select(WalletTransaction)
            .where(
                WalletTransaction.transaction_id == transaction_id,
                WalletTransaction.type == kind,
                WalletTransaction.note == note,
                WalletTransaction.is_credit.is_(is_credit),
            )
            .limit(1)
        )
    ).scalar_one_or_none()


async def apply_ledger(
    db: AsyncSession,
    *,
    kind: str,
    owner_id: UUID,
    user_id: UUID | None,
    amount: Decimal,
    is_credit: bool,
    note: str,
    transaction_id: str,
    payment_type: str | None,
) -> tuple[WalletTransaction, bool]:
    """Credit or debit one wallet. Returns (row, created)."""
    if kind not in {"customer", "provider"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ledger type")
    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be greater than 0")

    existing = await find_existing(
        db, transaction_id=transaction_id, kind=kind, note=note, is_credit=is_credit
    )
    if existing is not None:
        return existing, False

    delta = amount if is_credit else -amount
    now = datetime.now(UTC)

    if kind == "customer":
        customer = (
            await db.execute(select(Customer).where(Customer.id == owner_id).with_for_update())
        ).scalar_one_or_none()
        if customer is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
        again = await find_existing(
            db, transaction_id=transaction_id, kind=kind, note=note, is_credit=is_credit
        )
        if again is not None:
            return again, False
        current = parse_money(customer.wallet_amount)
        customer.wallet_amount = current + delta
        row = WalletTransaction(
            id=uuid4(),
            amount=format_provider_wallet(amount),
            created_date=now,
            is_credit=is_credit,
            note=note,
            payment_type=payment_type,
            transaction_id=transaction_id,
            type="customer",
            user_id=user_id or customer.user_id or customer.id,
            customer_id=customer.id,
        )
    else:
        provider = (
            await db.execute(select(Provider).where(Provider.id == owner_id).with_for_update())
        ).scalar_one_or_none()
        if provider is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
        again = await find_existing(
            db, transaction_id=transaction_id, kind=kind, note=note, is_credit=is_credit
        )
        if again is not None:
            return again, False
        current = parse_money(provider.wallet_amount)
        provider.wallet_amount = format_provider_wallet(current + delta)
        row = WalletTransaction(
            id=uuid4(),
            amount=format_provider_wallet(amount),
            created_date=now,
            is_credit=is_credit,
            note=note,
            payment_type=payment_type,
            transaction_id=transaction_id,
            type="provider",
            user_id=user_id or provider.user_id,
            provider_id=provider.id,
        )

    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row, True
