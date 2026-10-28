from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.payments import WithdrawalCreateBody
from app.api.v1.schemas.wallet import WalletTransactionOut, WithdrawalOut
from app.core.security.deps import RequireAuth, RequireProvider
from app.core.security.payments import require_payment_writes
from app.core.services import payment_writes, wallet_service
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/wallet", tags=["Wallet"])


@router.get(
    "/transactions",
    response_model=Page[WalletTransactionOut],
    operation_id="wallet_list_transactions",
    summary="Read-only wallet ledger for the authenticated user",
)
async def list_transactions(
    ctx: RequireAuth,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[WalletTransactionOut]:
    rows = await wallet_service.list_wallet_transactions(
        db,
        user_id=ctx.user_id,
        customer_id=ctx.customer_id,
        provider_id=ctx.provider_id,
        limit=limit,
        offset=offset,
    )
    return Page(
        items=[WalletTransactionOut.model_validate(r) for r in rows],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.get(
    "/withdrawals",
    response_model=Page[WithdrawalOut],
    operation_id="wallet_list_withdrawals",
    summary="Read-only withdrawal history for the authenticated provider",
)
async def list_withdrawals(
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[WithdrawalOut]:
    assert ctx.provider_id is not None
    rows = await wallet_service.list_withdrawals_for_provider(
        db, ctx.provider_id, limit=limit, offset=offset
    )
    return Page(
        items=[WithdrawalOut.model_validate(r) for r in rows],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.post(
    "/withdrawals",
    response_model=WithdrawalOut,
    operation_id="wallet_request_withdrawal",
    summary="Create a pending withdrawal from an owned payout method (no debit until admin pays)",
)
async def request_withdrawal(
    body: WithdrawalCreateBody,
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WithdrawalOut:
    require_payment_writes()
    row = await payment_writes.request_withdrawal(
        db,
        ctx=ctx,
        amount=body.amount,
        payment_method_id=body.payment_method_id,
        note=body.note,
    )
    return WithdrawalOut.model_validate(row)


@router.post(
    "/withdrawals/{withdrawal_id}/cancel",
    response_model=WithdrawalOut,
    operation_id="wallet_cancel_withdrawal",
    summary="Cancel a pending withdrawal (rejected restores stay on Edge until cutover)",
)
async def cancel_withdrawal(
    withdrawal_id: UUID,
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WithdrawalOut:
    require_payment_writes()
    row = await payment_writes.cancel_pending_withdrawal(db, ctx=ctx, withdrawal_id=withdrawal_id)
    return WithdrawalOut.model_validate(row)
