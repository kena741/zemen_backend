"""Repository for Handyman staff persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.phone import get_phone_search_variants
from app.domain.provider import HandymanDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.identity import Handyman


class HandymanRepository(BaseRepository[Handyman, HandymanDomain]):
    model = Handyman

    def to_domain(self, entity: Handyman) -> HandymanDomain:
        is_act = entity.is_active if entity.is_active is not None else (entity.active if entity.active is not None else True)
        return HandymanDomain(
            id=entity.id,
            provider_id=entity.provider_id,
            user_id=entity.user_id,
            first_name=entity.first_name,
            last_name=entity.last_name,
            email=entity.email,
            phone_number=entity.phone_number,
            user_name=entity.user_name,
            profile_image=entity.profile_image,
            active=is_act,
            created_at=entity.created_at,
            category_id=entity.category_id,
            sub_category_id=entity.sub_category_id,
            address=entity.address,
            fcm_token=entity.fcm_token,
        )

    def to_model(self, domain: HandymanDomain) -> Handyman:
        now = datetime.now(timezone.utc)
        return Handyman(
            id=domain.id,
            provider_id=domain.provider_id,
            user_id=domain.user_id,
            first_name=domain.first_name,
            last_name=domain.last_name,
            email=domain.email.lower().strip() if domain.email else None,
            phone_number=domain.phone_number,
            user_name=domain.user_name,
            profile_image=domain.profile_image,
            active=domain.active,
            is_active=domain.active,
            created_at=domain.created_at or now,
            category_id=domain.category_id,
            sub_category_id=domain.sub_category_id,
            address=domain.address,
            fcm_token=domain.fcm_token,
        )

    async def get_by_user_id(self, user_id: UUID) -> HandymanDomain | None:
        stmt = select(self.model).where(self.model.user_id == user_id)
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()
        return self.to_domain(entity) if entity else None

    async def get_by_phone(self, phone: str) -> HandymanDomain | None:
        variants = get_phone_search_variants(phone)
        stmt = select(self.model).where(self.model.phone_number.in_(variants))
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()
        return self.to_domain(entity) if entity else None

    async def list_by_provider(
        self,
        provider_id: UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> list[HandymanDomain]:
        stmt = (
            select(self.model)
            .where(self.model.provider_id == provider_id)
            .order_by(self.model.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return [self.to_domain(r) for r in res.scalars().all()]

    async def create_handyman(self, domain: HandymanDomain) -> HandymanDomain:
        entity = self.to_model(domain)
        self.session.add(entity)
        await self.session.flush()
        return self.to_domain(entity)

    async def update_handyman(
        self,
        handyman_id: UUID,
        provider_id: UUID,
        values: dict[str, Any],
    ) -> HandymanDomain | None:
        clean = {k: v for k, v in values.items() if hasattr(self.model, k) and v is not None}
        if "phone_number" in clean:
            from app.core.utils.phone import normalize_ethiopian_phone
            clean["phone_number"] = normalize_ethiopian_phone(clean["phone_number"])
        stmt = (
            update(self.model)
            .where(self.model.id == handyman_id)
            .where(self.model.provider_id == provider_id)
            .values(**clean)
            .returning(self.model)
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        updated = res.scalar_one_or_none()
        return self.to_domain(updated) if updated else None

    async def delete_handyman(self, handyman_id: UUID, provider_id: UUID) -> bool:
        stmt = (
            delete(self.model)
            .where(self.model.id == handyman_id)
            .where(self.model.provider_id == provider_id)
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount > 0

