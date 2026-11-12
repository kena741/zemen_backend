"""Repository for Marketing Banners."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.domain.content import BannerDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.config import Banner


class BannerRepository(BaseRepository[Banner, BannerDomain]):
    model = Banner

    def to_domain(self, entity: Banner) -> BannerDomain:
        return BannerDomain(
            id=entity.id,
            banner_name=entity.banner_name,
            image=entity.image,
            link=entity.link,
            active=entity.active,
            created_at=entity.created_at,
        )

    async def list_all_banners(self) -> list[BannerDomain]:
        stmt = select(self.model).order_by(self.model.created_at.desc())
        res = await self.session.execute(stmt)
        return [self.to_domain(b) for b in res.scalars().all()]
