"""Repository for Provider Payment Methods (Bank details)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update

from app.domain.provider import BankMethodDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.finance import ProviderPaymentMethod


class ProviderBankRepository(BaseRepository[ProviderPaymentMethod, BankMethodDomain]):
    model = ProviderPaymentMethod

    def to_domain(self, entity: ProviderPaymentMethod) -> BankMethodDomain:
        return BankMethodDomain(
            id=entity.id,
            provider_id=entity.provider_id,
            method_type=entity.method_type,
            method_code=entity.method_code,
            method_name=entity.method_name,
            holder_name=entity.holder_name,
            account_number=entity.account_number,
            swift_code=entity.swift_code,
            bank_name=entity.bank_name,
            branch_city=entity.branch_city,
            branch_country=entity.branch_country,
            is_active=entity.is_active,
            is_default=entity.is_default,
            currency=entity.currency,
            metadata=entity.metadata_ or {},
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def list_for_provider(self, provider_id: UUID) -> list[BankMethodDomain]:
        stmt = (
            select(self.model)
            .where(self.model.provider_id == provider_id, self.model.method_type == "bank")
            .order_by(self.model.is_default.desc(), self.model.updated_at.desc())
        )
        res = await self.session.execute(stmt)
        return [self.to_domain(r) for r in res.scalars().all()]

    async def get_default(self, provider_id: UUID) -> BankMethodDomain | None:
        stmt = (
            select(self.model)
            .where(
                self.model.provider_id == provider_id,
                self.model.method_type == "bank",
                self.model.is_default.is_(True),
            )
            .limit(1)
        )
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()
        return self.to_domain(entity) if entity else None

    async def upsert_bank_details(
        self,
        provider_id: UUID,
        holder_name: str | None,
        account_number: str,
        bank_name: str | None,
        swift_code: str | None = None,
        branch_city: str | None = None,
        branch_country: str | None = None,
        method_code: str | None = None,
        method_id: UUID | None = None,
    ) -> BankMethodDomain:
        now = datetime.now(timezone.utc)
        clean_account = "".join(ch for ch in account_number if ch.isdigit())

        # Clear default flag on existing bank methods for this provider
        clear_stmt = (
            update(self.model)
            .where(self.model.provider_id == provider_id, self.model.method_type == "bank")
            .values(is_default=False, updated_at=now)
        )
        await self.session.execute(clear_stmt)

        # Check existing row by method_id or account number
        existing: ProviderPaymentMethod | None = None
        if method_id:
            res = await self.session.execute(
                select(self.model).where(self.model.id == method_id, self.model.provider_id == provider_id)
            )
            existing = res.scalar_one_or_none()
        if not existing and clean_account:
            res = await self.session.execute(
                select(self.model).where(
                    self.model.provider_id == provider_id,
                    self.model.account_number == clean_account,
                )
            )
            existing = res.scalar_one_or_none()

        m_code = method_code or "bank"
        m_name = bank_name or "Bank Transfer"

        if existing:
            existing.holder_name = holder_name
            existing.account_number = clean_account
            existing.bank_name = bank_name
            existing.swift_code = swift_code
            existing.branch_city = branch_city
            existing.branch_country = branch_country
            existing.method_code = m_code
            existing.method_name = m_name
            existing.is_default = True
            existing.is_active = True
            existing.currency = "ETB"
            existing.updated_at = now
            await self.session.flush()
            return self.to_domain(existing)

        new_entity = ProviderPaymentMethod(
            id=uuid4(),
            provider_id=provider_id,
            method_type="bank",
            method_code=m_code,
            method_name=m_name,
            holder_name=holder_name,
            account_number=clean_account,
            bank_name=bank_name,
            swift_code=swift_code,
            branch_city=branch_city,
            branch_country=branch_country,
            is_active=True,
            is_default=True,
            currency="ETB",
            metadata_={},
            created_at=now,
            updated_at=now,
        )
        self.session.add(new_entity)
        await self.session.flush()
        return self.to_domain(new_entity)
