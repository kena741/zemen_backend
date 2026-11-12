"""Repository for Company profiles linked to providers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from app.domain.provider import CompanyDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.identity import Company


class ProviderCompanyRepository(BaseRepository[Company, CompanyDomain]):
    model = Company

    def to_domain(self, entity: Company) -> CompanyDomain:
        return CompanyDomain(
            id=entity.id,
            provider_id=entity.provider_id,
            name=entity.name,
            website=entity.website,
            company_name=entity.company_name,
            industry=entity.industry,
            company_size=entity.company_size,
            headquarters=entity.headquarters,
            founded=entity.founded,
            profile_bio=entity.profile_bio,
            banner_image=entity.banner_image,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def get_by_provider_id(self, provider_id: UUID) -> CompanyDomain | None:
        stmt = select(self.model).where(self.model.provider_id == provider_id)
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()
        return self.to_domain(entity) if entity else None

    async def upsert_company(self, provider_id: UUID, values: dict[str, Any]) -> CompanyDomain:
        now = datetime.now(timezone.utc)
        stmt = select(self.model).where(self.model.provider_id == provider_id)
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()

        clean_vals = {k: (v if v != "" else None) for k, v in values.items()}
        if existing:
            for k, v in clean_vals.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
            existing.updated_at = now
            await self.session.flush()
            return self.to_domain(existing)

        new_entity = Company(
            id=uuid4(),
            provider_id=provider_id,
            name=clean_vals.get("name") or clean_vals.get("company_name") or "Company",
            website=clean_vals.get("website"),
            company_name=clean_vals.get("company_name"),
            industry=clean_vals.get("industry"),
            company_size=clean_vals.get("company_size"),
            headquarters=clean_vals.get("headquarters"),
            founded=clean_vals.get("founded"),
            profile_bio=clean_vals.get("profile_bio"),
            banner_image=clean_vals.get("banner_image"),
            created_at=now,
            updated_at=now,
        )
        self.session.add(new_entity)
        await self.session.flush()
        return self.to_domain(new_entity)
