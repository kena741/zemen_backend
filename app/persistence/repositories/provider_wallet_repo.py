"""Repository for Provider Wallet transaction queries."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import or_, select

from app.domain.provider import ProviderWalletStatsDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.finance import WalletTransaction
from app.persistence.sqlalchemy.models.identity import Provider


class ProviderWalletRepository(BaseRepository[WalletTransaction, dict[str, Any]]):
    model = WalletTransaction

    def to_domain(self, entity: WalletTransaction) -> dict[str, Any]:
        return {
            "id": str(entity.id),
            "amount": entity.amount,
            "createdDate": entity.created_date.isoformat() if entity.created_date else None,
            "isCredit": entity.is_credit,
            "note": entity.note,
            "paymentType": entity.payment_type,
            "transactionId": entity.transaction_id,
            "type": entity.type,
            "userId": str(entity.user_id) if entity.user_id else None,
            "providerId": str(entity.provider_id) if entity.provider_id else None,
        }

    async def get_wallet_history(
        self,
        provider_id: UUID,
        auth_user_id: UUID | None = None,
    ) -> tuple[list[dict[str, Any]], ProviderWalletStatsDomain]:
        filters = [self.model.provider_id == provider_id, self.model.user_id == provider_id]
        if auth_user_id:
            filters.append(self.model.user_id == auth_user_id)

        stmt = (
            select(self.model)
            .where(or_(*filters))
            .order_by(self.model.created_date.desc())
        )
        res = await self.session.execute(stmt)
        transactions = res.scalars().all()

        # Fetch provider's current stored wallet amount
        prov_res = await self.session.execute(
            select(Provider.wallet_amount).where(Provider.id == provider_id)
        )
        stored_raw = prov_res.scalar_one_or_none() or "0"
        try:
            stored_amount = float(stored_raw)
        except (ValueError, TypeError):
            stored_amount = 0.0

        ledger_net = 0.0
        rows: list[dict[str, Any]] = []
        for tx in transactions:
            row = self.to_domain(tx)
            rows.append(row)
            try:
                amt = float(tx.amount or 0)
                if tx.is_credit:
                    ledger_net += amt
                else:
                    ledger_net -= amt
            except (ValueError, TypeError):
                pass

        ledger_matches = abs(ledger_net - stored_amount) < 0.01

        stats = ProviderWalletStatsDomain(
            count=len(rows),
            ledger_net=round(ledger_net, 2),
            stored_wallet_amount=round(stored_amount, 2),
            ledger_matches_stored=ledger_matches,
        )

        return rows, stats
