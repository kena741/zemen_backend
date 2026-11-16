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

    def to_model(self, domain: ProviderDomain) -> Provider:
        now = datetime.now(timezone.utc)
        return Provider(
            id=domain.id,
            user_id=domain.user_id,
            email=domain.email.lower().strip() if domain.email else None,
            first_name=domain.first_name,
            last_name=domain.last_name,
            user_name=domain.user_name,
            phone_number=domain.phone_number,
            profile_image=domain.profile_image,
            banner=domain.banner,
            address=domain.address,
            country=domain.country,
            country_code=domain.country_code or "+251",
            currency=domain.currency or "ETB",
            location=domain.location,
            slug=domain.slug,
            user_type=domain.user_type or "provider",
            wallet_amount=str(domain.wallet_amount or "0"),
            active=domain.active,
            fcm_token=domain.fcm_token,
            social_links=domain.social_links if isinstance(domain.social_links, dict) else {},
            activation_paid=domain.activation_paid,
            activation_paid_at=domain.activation_paid_at,
            activation_tx_ref=domain.activation_tx_ref,
            provider_type=domain.provider_type or "individual",
            company_verification_status=domain.company_verification_status or "not_submitted",
            service_tier_max=domain.service_tier_max,
            service_tier_paid_at=domain.service_tier_paid_at,
            verified_subcategory_ids=domain.verified_subcategory_ids,
            signup_source=domain.signup_source or "mobile",
            profession_id=domain.profession_id,
            category_id=domain.category_id,
            company_license_url=domain.company_license_url,
            company_rejection_reason=domain.company_rejection_reason,
            service_tier_tx_ref=domain.service_tier_tx_ref,
            admin_note=domain.admin_note,
            created_at=domain.created_at or now,
            updated_at=domain.updated_at or now,
            archived_at=domain.archived_at,
        )

    async def get_by_user_id(self, user_id: UUID) -> ProviderDomain | None:
        stmt = (
            select(self.model)
            .where(self.model.user_id == user_id)
            .where(self.model.archived_at.is_(None))
        )
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()
        return self.to_domain(entity) if entity else None

    async def get_by_phone(self, phone: str) -> ProviderDomain | None:
        from app.core.utils.phone import get_phone_search_variants
        variants = get_phone_search_variants(phone)
        stmt = (
            select(self.model)
            .where(self.model.phone_number.in_(variants))
            .where(self.model.archived_at.is_(None))
        )
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()
        return self.to_domain(entity) if entity else None

    async def create_provider(self, domain: ProviderDomain) -> ProviderDomain:
        entity = self.to_model(domain)
        self.session.add(entity)
        await self.session.flush()
        return self.to_domain(entity)

    async def update_fcm_token(self, provider_id: UUID, fcm_token: str) -> None:
        stmt = (
            update(self.model)
            .where(self.model.id == provider_id)
            .values(fcm_token=fcm_token, updated_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def update_provider(self, provider_id: UUID, values: dict[str, Any]) -> ProviderDomain | None:
        clean = {k: v for k, v in values.items() if hasattr(self.model, k) and v is not None}
        if "phone_number" in clean:
            from app.core.utils.phone import normalize_ethiopian_phone
            clean["phone_number"] = normalize_ethiopian_phone(clean["phone_number"])
        clean["updated_at"] = datetime.now(timezone.utc)
        stmt = (
            update(self.model)
            .where(self.model.id == provider_id)
            .where(self.model.archived_at.is_(None))
            .values(**clean)
            .returning(self.model)
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        updated = res.scalar_one_or_none()
        return self.to_domain(updated) if updated else None

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
