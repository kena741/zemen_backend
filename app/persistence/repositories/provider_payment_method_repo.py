"""Repository for Provider Payment Methods."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update

from app.domain.finance import ProviderPaymentMethodDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.finance import ProviderPaymentMethod


class ProviderPaymentMethodRepository(BaseRepository[ProviderPaymentMethod, ProviderPaymentMethodDomain]):
    model = ProviderPaymentMethod

    def to_domain(self, entity: ProviderPaymentMethod) -> ProviderPaymentMethodDomain:
        return ProviderPaymentMethodDomain(
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

    async def list_for_providers(self, provider_ids: list[UUID]) -> list[ProviderPaymentMethodDomain]:
        if not provider_ids:
            return []
        stmt = (
            select(self.model)
            .where(self.model.provider_id.in_(provider_ids), self.model.is_active.is_(True))
            .order_by(self.model.is_default.desc())
        )
        res = await self.session.execute(stmt)
        return [self.to_domain(m) for m in res.scalars().all()]

    async def get_default_for_provider(self, provider_id: UUID) -> ProviderPaymentMethodDomain | None:
        stmt = (
            select(self.model)
            .where(
                self.model.provider_id == provider_id,
                self.model.is_active.is_(True),
            )
            .order_by(self.model.is_default.desc())
            .limit(1)
        )
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()
        return self.to_domain(entity) if entity else None

    async def upsert_payment_method(
        self,
        provider_id: UUID,
        bank_name: str,
        account_number: str,
        holder_name: str | None = None,
        swift_code: str | None = None,
        branch_city: str | None = None,
        branch_country: str | None = "Ethiopia",
        is_default: bool = True,
        method_code: str = "cbe",
        method_name: str = "Bank Transfer",
    ) -> ProviderPaymentMethodDomain:
        now = datetime.now(timezone.utc)
        if is_default:
            # Unset existing defaults for this provider
            await self.session.execute(
                update(self.model)
                .where(self.model.provider_id == provider_id)
                .values(is_default=False, updated_at=now)
            )

        # Check if identical account exists
        stmt = select(self.model).where(
            self.model.provider_id == provider_id,
            self.model.account_number == account_number,
        )
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            existing.bank_name = bank_name
            existing.holder_name = holder_name
            existing.swift_code = swift_code
            existing.branch_city = branch_city
            existing.branch_country = branch_country
            existing.is_default = is_default
            existing.is_active = True
            existing.updated_at = now
            await self.session.flush()
            return self.to_domain(existing)

        new_method = ProviderPaymentMethod(
            id=uuid4(),
            provider_id=provider_id,
            method_type="bank",
            method_code=method_code,
            method_name=method_name,
            holder_name=holder_name,
            account_number=account_number,
            swift_code=swift_code,
            bank_name=bank_name,
            branch_city=branch_city,
            branch_country=branch_country,
            is_active=True,
            is_default=is_default,
            currency="ETB",
            metadata_={},
            created_at=now,
            updated_at=now,
        )
        self.session.add(new_method)
        await self.session.flush()
        return self.to_domain(new_method)
