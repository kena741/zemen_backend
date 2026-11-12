"""Repository for Country Taxes."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.domain.finance import CountryTaxDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.config import CountryTax


class CountryTaxRepository(BaseRepository[CountryTax, CountryTaxDomain]):
    model = CountryTax

    def to_domain(self, entity: CountryTax) -> CountryTaxDomain:
        val = float(entity.value or 0.0)
        return CountryTaxDomain(
            id=entity.id,
            name=entity.name,
            country=entity.country,
            value=val,
            type=entity.type or "percentage",
            is_fix=bool(entity.is_fix),
            active=bool(entity.active if entity.active is not None else True),
            created_at=entity.created_at or datetime.now(timezone.utc),
        )

    async def list_all_taxes(self) -> list[CountryTaxDomain]:
        stmt = select(self.model).order_by(self.model.created_at.desc())
        res = await self.session.execute(stmt)
        return [self.to_domain(t) for t in res.scalars().all()]
