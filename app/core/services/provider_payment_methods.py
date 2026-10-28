"""Provider payout methods. `providerID` is always the authenticated provider row id."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import ProviderPaymentMethod

WRITE_FIELDS = frozenset(
    {
        "method_type",
        "method_code",
        "method_name",
        "holder_name",
        "account_number",
        "swift_code",
        "bank_name",
        "branch_city",
        "branch_country",
        "is_active",
        "is_default",
        "currency",
    }
)


class PaymentMethodConflict(Exception):
    pass


async def list_for_provider(db: AsyncSession, provider_id: UUID) -> list[ProviderPaymentMethod]:
    stmt = (
        select(ProviderPaymentMethod)
        .where(ProviderPaymentMethod.provider_id == provider_id)
        .order_by(ProviderPaymentMethod.is_default.desc(), ProviderPaymentMethod.updated_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_owned(
    db: AsyncSession, provider_id: UUID, method_id: UUID
) -> ProviderPaymentMethod | None:
    return (
        await db.execute(
            select(ProviderPaymentMethod).where(
                ProviderPaymentMethod.id == method_id,
                ProviderPaymentMethod.provider_id == provider_id,
            )
        )
    ).scalar_one_or_none()


async def _clear_default(db: AsyncSession, provider_id: UUID, keep: UUID | None = None) -> None:
    stmt = (
        update(ProviderPaymentMethod)
        .where(
            ProviderPaymentMethod.provider_id == provider_id,
            ProviderPaymentMethod.is_default.is_(True),
        )
        .values(is_default=False)
    )
    if keep is not None:
        stmt = stmt.where(ProviderPaymentMethod.id != keep)
    await db.execute(stmt)


def _apply(row: ProviderPaymentMethod, data: dict[str, Any]) -> None:
    for key, value in data.items():
        if key in WRITE_FIELDS:
            setattr(row, key, value)


async def upsert(
    db: AsyncSession, provider_id: UUID, data: dict[str, Any], *, method_id: UUID | None = None
) -> ProviderPaymentMethod:
    now = datetime.now(UTC)
    payload = {k: v for k, v in data.items() if k in WRITE_FIELDS}
    payload.setdefault("method_type", "bank")
    payload.setdefault("is_active", True)
    payload.setdefault("currency", "ETB")
    if not payload.get("method_name"):
        payload["method_name"] = payload.get("bank_name") or "Bank"
    if not payload.get("method_code"):
        payload["method_code"] = str(payload["method_name"]).lower().replace(" ", "_")
    if not payload.get("account_number"):
        raise ValueError("accountNumber is required")

    row = await get_owned(db, provider_id, method_id) if method_id else None
    if row is None and payload.get("account_number"):
        row = (
            await db.execute(
                select(ProviderPaymentMethod).where(
                    ProviderPaymentMethod.provider_id == provider_id,
                    ProviderPaymentMethod.method_type == payload["method_type"],
                    ProviderPaymentMethod.account_number == payload["account_number"],
                )
            )
        ).scalar_one_or_none()

    make_default = payload.pop("is_default", True)
    if row is None:
        row = ProviderPaymentMethod(
            id=uuid4(),
            provider_id=provider_id,
            metadata_={},
            created_at=now,
            is_default=False,
            **payload,
        )
        db.add(row)
        await db.flush()
    else:
        _apply(row, payload)
        row.updated_at = now
        await db.flush()

    if make_default is not False:
        await _clear_default(db, provider_id, keep=row.id)
        row.is_default = True
    row.updated_at = now
    try:
        await db.flush()
    except IntegrityError as exc:
        raise PaymentMethodConflict("A payment method with this account already exists") from exc
    await db.refresh(row)
    return row


async def delete_owned(db: AsyncSession, row: ProviderPaymentMethod) -> None:
    await db.delete(row)
    await db.flush()
