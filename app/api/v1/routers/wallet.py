"""Wallet routes for balances, ledger transactions, provider payout methods, and withdrawals."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.payments import WithdrawalCreateBody
from app.api.v1.schemas.wallet import (
    ProviderPaymentMethodCreate,
    ProviderPaymentMethodOut,
    WalletBalanceOut,
    WalletTransactionOut,
    WithdrawalOut,
)
from app.core.security.deps import RequireAuth, RequireProvider
from app.core.services import payment_writes
from app.core.services.wallet_service import WalletService
from app.persistence.repositories.customer_repo import CustomerRepository
from app.persistence.repositories.provider_payment_method_repo import ProviderPaymentMethodRepository
from app.persistence.repositories.provider_repo import ProviderRepository
from app.persistence.repositories.wallet_transaction_repo import WalletTransactionRepository
from app.persistence.repositories.withdrawal_repo import WithdrawalRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/wallet", tags=["Wallet"])


def get_wallet_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WalletService:
    return WalletService(
        wallet_tx_repo=WalletTransactionRepository(db),
        withdrawal_repo=WithdrawalRepository(db),
        payment_method_repo=ProviderPaymentMethodRepository(db),
        customer_repo=CustomerRepository(db),
        provider_repo=ProviderRepository(db),
    )


# ======================== Balance & Transactions ========================


@router.get(
    "/balance",
    response_model=WalletBalanceOut,
    summary="Get current wallet balance for the authenticated user",
)
async def get_wallet_balance(
    ctx: RequireAuth,
    service: Annotated[WalletService, Depends(get_wallet_service)],
) -> WalletBalanceOut:
    bal = await service.get_balance(
        user_id=ctx.user_id,
        customer_id=ctx.customer_id,
        provider_id=ctx.provider_id,
    )
    return WalletBalanceOut(balance=bal, currency="ETB")


@router.get(
    "/transactions",
    response_model=Page[WalletTransactionOut],
    summary="List wallet ledger transactions for the authenticated user",
)
async def list_transactions(
    ctx: RequireAuth,
    service: Annotated[WalletService, Depends(get_wallet_service)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[WalletTransactionOut]:
    rows = await service.list_transactions(
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


# ======================== Provider Withdrawals & Payout Methods ========================


@router.get(
    "/withdrawals",
    response_model=Page[WithdrawalOut],
    summary="List withdrawal request history for the authenticated provider",
)
async def list_withdrawals(
    ctx: RequireProvider,
    service: Annotated[WalletService, Depends(get_wallet_service)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[WithdrawalOut]:
    assert ctx.provider_id is not None
    rows = await service.list_withdrawals(
        provider_id=ctx.provider_id,
        limit=limit,
        offset=offset,
    )
    return Page(
        items=[WithdrawalOut.model_validate(r) for r in rows],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.post(
    "/withdrawals",
    response_model=WithdrawalOut,
    status_code=status.HTTP_201_CREATED,
    summary="Provider submits a withdrawal request with balance validation",
)
async def request_withdrawal(
    body: WithdrawalCreateBody,
    ctx: RequireProvider,
    service: Annotated[WalletService, Depends(get_wallet_service)],
) -> WithdrawalOut:
    assert ctx.provider_id is not None
    withdrawal = await service.request_withdrawal(
        provider_id=ctx.provider_id,
        amount=float(body.amount),
        payment_method_id=str(body.payment_method_id) if body.payment_method_id else None,
        note=body.note,
    )
    return WithdrawalOut.model_validate(withdrawal)


@router.post(
    "/withdrawals/{withdrawal_id}/cancel",
    response_model=WithdrawalOut,
    operation_id="wallet_cancel_withdrawal",
    summary="Cancel a pending withdrawal request",
)
async def cancel_withdrawal(
    withdrawal_id: UUID,
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WithdrawalOut:
    row = await payment_writes.cancel_pending_withdrawal(db, ctx=ctx, withdrawal_id=withdrawal_id)
    return WithdrawalOut.model_validate(row)


@router.get(
    "/payment-methods",
    response_model=list[ProviderPaymentMethodOut],
    summary="List registered payout bank accounts for the authenticated provider",
)
async def list_payment_methods(
    ctx: RequireProvider,
    service: Annotated[WalletService, Depends(get_wallet_service)],
) -> list[ProviderPaymentMethodOut]:
    assert ctx.provider_id is not None
    methods = await service.list_payment_methods(provider_id=ctx.provider_id)
    return [ProviderPaymentMethodOut.model_validate(m) for m in methods]


@router.post(
    "/payment-methods",
    response_model=ProviderPaymentMethodOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new payout bank account for the authenticated provider",
)
async def create_payment_method(
    body: ProviderPaymentMethodCreate,
    ctx: RequireProvider,
    service: Annotated[WalletService, Depends(get_wallet_service)],
) -> ProviderPaymentMethodOut:
    assert ctx.provider_id is not None
    method = await service.create_payment_method(
        provider_id=ctx.provider_id,
        data=body.model_dump(exclude_unset=True),
    )
    return ProviderPaymentMethodOut.model_validate(method)


@router.delete(
    "/payment-methods/{method_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate or remove a payout bank account",
)
async def delete_payment_method(
    method_id: UUID,
    ctx: RequireProvider,
    service: Annotated[WalletService, Depends(get_wallet_service)],
) -> None:
    assert ctx.provider_id is not None
    await service.delete_payment_method(provider_id=ctx.provider_id, method_id=method_id)
