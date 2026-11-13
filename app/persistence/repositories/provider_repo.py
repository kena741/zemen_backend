"""Repository for Provider persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update

from app.domain.provider import ProviderDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.catalog import Service
from app.persistence.sqlalchemy.models.identity import Provider


class ProviderRepository(BaseRepository[Provider, ProviderDomain]):
    model = Provider

    def to_domain(self, entity: Provider) -> ProviderDomain:
        return ProviderDomain(
            id=entity.id,
            user_id=entity.user_id,
            email=entity.email,
            first_name=entity.first_name,
            last_name=entity.last_name,
            user_name=entity.user_name,
            phone_number=entity.phone_number,
            profile_image=entity.profile_image,
            banner=entity.banner,
            address=entity.address,
            country=entity.country,
            country_code=entity.country_code,
            currency=entity.currency,
            location=entity.location,
            slug=entity.slug,
            user_type=entity.user_type,
            wallet_amount=entity.wallet_amount,
            active=entity.active,
            fcm_token=entity.fcm_token,
            social_links=entity.social_links or {},
            activation_paid=entity.activation_paid,
            activation_paid_at=entity.activation_paid_at,
            activation_tx_ref=entity.activation_tx_ref,
            provider_type=entity.provider_type,
            company_verification_status=entity.company_verification_status,
            service_tier_max=entity.service_tier_max,
            service_tier_paid_at=entity.service_tier_paid_at,
            verified_subcategory_ids=list(entity.verified_subcategory_ids or []),
            signup_source=entity.signup_source,
            profession_id=entity.profession_id,
            category_id=entity.category_id,
            company_license_url=entity.company_license_url,
            company_rejection_reason=entity.company_rejection_reason,
            service_tier_tx_ref=entity.service_tier_tx_ref,
            admin_note=entity.admin_note,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            archived_at=entity.archived_at,
        )

    async def list_providers(
        self,
        include_archived: bool = True,
        offset: int = 0,
        limit: int = 1000,
    ) -> list[ProviderDomain]:
        stmt = select(self.model)
        if not include_archived:
            stmt = stmt.where(self.model.archived_at.is_(None))
        stmt = stmt.order_by(self.model.created_at.desc()).offset(offset).limit(limit)
        res = await self.session.execute(stmt)
        return [self.to_domain(r) for r in res.scalars().all()]

    async def get_by_email(self, email: str) -> ProviderDomain | None:
        stmt = select(self.model).where(func.lower(self.model.email) == email.lower().strip())
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()
        return self.to_domain(entity) if entity else None

    async def get_by_slug(self, slug: str) -> ProviderDomain | None:
        stmt = select(self.model).where(self.model.slug == slug.strip())
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()
        return self.to_domain(entity) if entity else None

    async def archive(self, provider_id: UUID, should_archive: bool) -> ProviderDomain | None:
        new_archived_at = datetime.now(timezone.utc) if should_archive else None
        stmt = (
            update(self.model)
            .where(self.model.id == provider_id)
            .values(archived_at=new_archived_at, updated_at=datetime.now(timezone.utc))
            .returning(self.model)
        )
        res = await self.session.execute(stmt)
        updated = res.scalar_one_or_none()
        return self.to_domain(updated) if updated else None

    async def count_services_by_provider(self) -> dict[str, int]:
        stmt = (
            select(Service.provider_id, func.count(Service.id))
            .where(Service.is_archived.isnot(True))
            .group_by(Service.provider_id)
        )
        res = await self.session.execute(stmt)
        return {str(row[0]): int(row[1]) for row in res.all() if row[0]}
