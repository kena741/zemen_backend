"""Repository for Wallet Transactions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.domain.finance import EnrichedWalletTransactionDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.finance import WalletTransaction
from app.persistence.sqlalchemy.models.users import User


class WalletTransactionRepository(BaseRepository[WalletTransaction, EnrichedWalletTransactionDomain]):
    model = WalletTransaction

    def to_domain(
        self,
        entity: WalletTransaction,
        user_full_name: str | None = None,
        user_email: str | None = None,
    ) -> EnrichedWalletTransactionDomain:
        return EnrichedWalletTransactionDomain(
            id=entity.id,
            amount=entity.amount,
            is_credit=entity.is_credit,
            note=entity.note,
            payment_type=entity.payment_type,
            transaction_id=entity.transaction_id,
            type=entity.type,
            user_id=entity.user_id,
            provider_id=entity.provider_id,
            customer_id=entity.customer_id,
            user_full_name=user_full_name,
            user_email=user_email,
            created_date=entity.created_date,
        )

    async def list_enriched(
        self,
        offset: int = 0,
        limit: int = 50,
    ) -> list[EnrichedWalletTransactionDomain]:
        stmt = (
            select(
                WalletTransaction,
                User.phone.label("u_phone"),
                User.email.label("u_email"),
            )
            .outerjoin(User, WalletTransaction.user_id == User.id)
            .order_by(WalletTransaction.created_date.desc().nullslast())
            .offset(offset)
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        items: list[EnrichedWalletTransactionDomain] = []
        for tx, u_phone, u_email in res.all():
            items.append(
                self.to_domain(
                    tx,
                    user_full_name=u_phone or "User",
                    user_email=u_email,
                )
            )
        return items
