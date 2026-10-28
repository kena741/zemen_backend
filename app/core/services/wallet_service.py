from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import WalletTransaction, WithdrawalHistory


async def list_wallet_transactions(
    db: AsyncSession,
    *,
    user_id: UUID,
    customer_id: UUID | None,
    provider_id: UUID | None,
    limit: int = 50,
    offset: int = 0,
) -> list[WalletTransaction]:
    clauses = [WalletTransaction.user_id == user_id]
    if customer_id is not None:
        clauses.append(WalletTransaction.customer_id == customer_id)
    if provider_id is not None:
        clauses.append(WalletTransaction.provider_id == provider_id)
    stmt = (
        select(WalletTransaction)
        .where(or_(*clauses))
        .order_by(WalletTransaction.created_date.desc())
        .limit(min(limit, 100))
        .offset(max(offset, 0))
    )
    return list((await db.execute(stmt)).scalars().all())


async def list_withdrawals_for_provider(
    db: AsyncSession, provider_id: UUID, *, limit: int = 50, offset: int = 0
) -> list[WithdrawalHistory]:
    stmt = (
        select(WithdrawalHistory)
        .where(WithdrawalHistory.provider_id == provider_id)
        .order_by(WithdrawalHistory.created_date.desc())
        .limit(min(limit, 100))
        .offset(max(offset, 0))
    )
    return list((await db.execute(stmt)).scalars().all())
