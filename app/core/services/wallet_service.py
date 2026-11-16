"""Wallet transactions, balance queries, withdrawal lifecycle, and payout methods."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import EntityNotFoundError, ValidationError
from app.domain.finance import (
    EnrichedWalletTransactionDomain,
    ProviderPaymentMethodDomain,
    WithdrawalDomain,
)
from app.persistence.repositories.customer_repo import CustomerRepository
from app.persistence.repositories.provider_payment_method_repo import ProviderPaymentMethodRepository
from app.persistence.repositories.provider_repo import ProviderRepository
from app.persistence.repositories.wallet_transaction_repo import WalletTransactionRepository
from app.persistence.repositories.withdrawal_repo import WithdrawalRepository
from app.persistence.sqlalchemy.models import WalletTransaction, WithdrawalHistory


class WalletService:
    def __init__(
        self,
        wallet_tx_repo: WalletTransactionRepository,
        withdrawal_repo: WithdrawalRepository,
        payment_method_repo: ProviderPaymentMethodRepository,
        customer_repo: CustomerRepository,
        provider_repo: ProviderRepository,
    ) -> None:
        self.wallet_tx_repo = wallet_tx_repo
        self.withdrawal_repo = withdrawal_repo
        self.payment_method_repo = payment_method_repo
        self.customer_repo = customer_repo
        self.provider_repo = provider_repo

    async def get_balance(
        self,
        user_id: UUID,
        customer_id: UUID | None = None,
        provider_id: UUID | None = None,
    ) -> float:
        if customer_id:
            cust = await self.customer_repo.get_by_id(customer_id)
            if cust and cust.wallet_amount:
                return float(cust.wallet_amount)
        if provider_id:
            prov = await self.provider_repo.get_by_id(provider_id)
            if prov and prov.wallet_amount:
                try:
                    return float(prov.wallet_amount)
                except (ValueError, TypeError):
                    return 0.0
        return 0.0

    async def list_transactions(
        self,
        user_id: UUID,
        customer_id: UUID | None = None,
        provider_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EnrichedWalletTransactionDomain]:
        return await self.wallet_tx_repo.list_for_actor(
            user_id=user_id,
            customer_id=customer_id,
            provider_id=provider_id,
            limit=limit,
            offset=offset,
        )

    async def list_withdrawals(
        self,
        provider_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[WithdrawalDomain]:
        return await self.withdrawal_repo.list_withdrawals(
            provider_id=provider_id,
            limit=limit,
            offset=offset,
        )

    async def request_withdrawal(
        self,
        provider_id: UUID,
        amount: float,
        payment_method_id: str | None = None,
        note: str | None = None,
    ) -> WithdrawalDomain:
        if amount <= 0:
            raise ValidationError("Withdrawal amount must be greater than 0.")

        prov = await self.provider_repo.get_by_id(provider_id)
        if not prov:
            raise EntityNotFoundError("Provider", provider_id)

        try:
            curr_bal = float(prov.wallet_amount or 0.0)
        except (ValueError, TypeError):
            curr_bal = 0.0

        if curr_bal < amount:
            raise ValidationError(
                f"Insufficient wallet balance. Available: {curr_bal:.2f} ETB, requested: {amount:.2f} ETB."
            )

        # Retrieve payment method details if specified
        bank_name, account_number, holder_name = None, None, None
        if payment_method_id:
            try:
                pm = await self.payment_method_repo.get_by_id(UUID(str(payment_method_id)))
                if pm:
                    bank_name = pm.bank_name
                    account_number = pm.account_number
                    holder_name = pm.holder_name
            except Exception:
                pass

        # Deduct from provider balance
        new_bal = curr_bal - amount
        await self.provider_repo.update_provider(
            provider_id=provider_id,
            values={"wallet_amount": str(new_bal)},
        )

        # Create withdrawal record
        withdrawal = await self.withdrawal_repo.create_withdrawal(
            provider_id=provider_id,
            amount=amount,
            payment_method_id=str(payment_method_id) if payment_method_id else None,
            note=note,
            bank_name=bank_name,
            account_number=account_number,
            holder_name=holder_name,
        )

        # Log debit transaction in wallet ledger
        now = datetime.now(timezone.utc)
        debit_tx = WalletTransaction(
            id=uuid4(),
            provider_id=provider_id,
            user_id=prov.user_id,
            amount=str(amount),
            is_credit=False,
            type="provider",
            payment_type="payout",
            transaction_id=str(withdrawal.id),
            note=note or f"Withdrawal request of {amount:.2f} ETB",
            created_date=now,
        )
        self.wallet_tx_repo.session.add(debit_tx)
        await self.wallet_tx_repo.session.commit()

        return withdrawal

    async def list_payment_methods(self, provider_id: UUID) -> list[ProviderPaymentMethodDomain]:
        return await self.payment_method_repo.list_for_providers([provider_id])

    async def create_payment_method(
        self, provider_id: UUID, data: dict[str, Any]
    ) -> ProviderPaymentMethodDomain:
        bank_name = data.get("bank_name") or data.get("bankName") or "Bank"
        acc_num = data.get("account_number") or data.get("accountNumber") or ""
        holder_name = data.get("holder_name") or data.get("holderName") or None
        if not acc_num:
            raise ValidationError("account_number is required.")

        return await self.payment_method_repo.upsert_payment_method(
            provider_id=provider_id,
            bank_name=bank_name,
            account_number=acc_num,
            holder_name=holder_name,
        )

    async def delete_payment_method(self, provider_id: UUID, method_id: UUID) -> bool:
        deleted = await self.payment_method_repo.delete_payment_method(
            provider_id=provider_id, method_id=method_id
        )
        if not deleted:
            raise EntityNotFoundError("Payment method", method_id)
        return True


# ======================== Legacy / Function Compatibility ========================


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
        .order_by(WalletTransaction.created_date.desc().nullslast())
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
        .order_by(WithdrawalHistory.created_date.desc().nullslast())
        .limit(min(limit, 100))
        .offset(max(offset, 0))
    )
    return list((await db.execute(stmt)).scalars().all())
