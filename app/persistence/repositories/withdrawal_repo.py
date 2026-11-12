"""Repository for Withdrawal History and Payout Requests."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update

from app.domain.finance import WithdrawalDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.finance import WithdrawalHistory
from app.persistence.sqlalchemy.models.identity import Provider


class WithdrawalRepository(BaseRepository[WithdrawalHistory, WithdrawalDomain]):
    model = WithdrawalHistory

    def to_domain(
        self,
        entity: WithdrawalHistory,
        provider_name: str | None = None,
        provider_phone: str | None = None,
        provider_email: str | None = None,
    ) -> WithdrawalDomain:
        amount_val = 0.0
        if entity.amount is not None:
            try:
                amount_val = float(entity.amount)
            except (ValueError, TypeError):
                amount_val = 0.0

        return WithdrawalDomain(
            id=entity.id,
            provider_id=entity.provider_id,
            amount=amount_val,
            payment_status=entity.payment_status or "pending",
            admin_note=entity.admin_note,
            note=entity.note,
            payment_date=entity.payment_date,
            payment_method_id=entity.payment_method_id,
            holder_name=entity.holder_name,
            bank_name=entity.bank_name,
            account_number=entity.account_number,
            swift_code=entity.swift_code,
            rejection_reason=entity.rejection_reason,
            provider_name=provider_name or "Provider",
            provider_phone=provider_phone,
            provider_email=provider_email,
            created_date=entity.created_date or datetime.now(timezone.utc),
        )

    async def list_withdrawals(
        self,
        statuses: list[str] | None = None,
        provider_id: UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[WithdrawalDomain]:
        stmt = (
            select(
                WithdrawalHistory,
                Provider.first_name.label("p_first"),
                Provider.last_name.label("p_last"),
                Provider.user_name.label("p_user"),
                Provider.phone_number.label("p_phone"),
                Provider.email.label("p_email"),
            )
            .outerjoin(Provider, WithdrawalHistory.provider_id == Provider.id)
            .order_by(WithdrawalHistory.created_date.desc())
            .offset(offset)
            .limit(limit)
        )

        if statuses:
            stmt = stmt.where(WithdrawalHistory.payment_status.in_(statuses))
        if provider_id:
            stmt = stmt.where(WithdrawalHistory.provider_id == provider_id)

        res = await self.session.execute(stmt)
        items: list[WithdrawalDomain] = []
        for w, p_first, p_last, p_user, p_phone, p_email in res.all():
            prov_name = f"{p_first or ''} {p_last or ''}".strip() or p_user or "Provider"
            items.append(
                self.to_domain(
                    w,
                    provider_name=prov_name,
                    provider_phone=p_phone,
                    provider_email=p_email,
                )
            )
        return items

    async def get_by_id_enriched(self, withdrawal_id: UUID) -> WithdrawalDomain | None:
        stmt = (
            select(
                WithdrawalHistory,
                Provider.first_name.label("p_first"),
                Provider.last_name.label("p_last"),
                Provider.user_name.label("p_user"),
                Provider.phone_number.label("p_phone"),
                Provider.email.label("p_email"),
            )
            .outerjoin(Provider, WithdrawalHistory.provider_id == Provider.id)
            .where(WithdrawalHistory.id == withdrawal_id)
        )
        res = await self.session.execute(stmt)
        row = res.first()
        if not row:
            return None
        w, p_first, p_last, p_user, p_phone, p_email = row
        prov_name = f"{p_first or ''} {p_last or ''}".strip() or p_user or "Provider"
        return self.to_domain(
            w,
            provider_name=prov_name,
            provider_phone=p_phone,
            provider_email=p_email,
        )

    async def update_status(
        self,
        withdrawal_id: UUID,
        status: str,
        admin_note: str | None = None,
        rejection_reason: str | None = None,
    ) -> WithdrawalHistory | None:
        values: dict[str, Any] = {"payment_status": status}
        if admin_note is not None:
            values["admin_note"] = admin_note
        if rejection_reason is not None:
            values["rejection_reason"] = rejection_reason

        stmt = (
            update(self.model)
            .where(self.model.id == withdrawal_id)
            .values(**values)
            .returning(self.model)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def mark_completed(
        self,
        withdrawal_id: UUID,
        admin_note: str | None = None,
    ) -> WithdrawalHistory | None:
        values: dict[str, Any] = {
            "payment_status": "completed",
            "payment_date": datetime.now(timezone.utc).isoformat(),
        }
        if admin_note is not None:
            values["admin_note"] = admin_note

        stmt = (
            update(self.model)
            .where(self.model.id == withdrawal_id)
            .values(**values)
            .returning(self.model)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def count_pending_badge(self) -> int:
        stmt = select(func.count(self.model.id)).where(self.model.payment_status.ilike("pending"))
        res = await self.session.execute(stmt)
        return int(res.scalar_one() or 0)
