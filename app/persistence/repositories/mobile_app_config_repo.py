"""Repository for Mobile App Configs (Maintenance & Force Update)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update

from app.domain.settings import MobileAppConfigDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.config import MobileAppConfig


class MobileAppConfigRepository(BaseRepository[MobileAppConfig, MobileAppConfigDomain]):
    model = MobileAppConfig

    def to_domain(self, entity: MobileAppConfig) -> MobileAppConfigDomain:
        return MobileAppConfigDomain(
            app_key=entity.app_key,
            maintenance_mode=entity.maintenance_mode,
            maintenance_message=entity.maintenance_message,
            maintenance_affected_versions=entity.maintenance_affected_versions or [],
            update_needed=entity.update_needed,
            update_message=entity.update_message,
            update_affected_versions=entity.update_affected_versions or [],
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def list_configs(self) -> list[MobileAppConfigDomain]:
        stmt = select(self.model).order_by(self.model.app_key.asc())
        res = await self.session.execute(stmt)
        return [self.to_domain(r) for r in res.scalars().all()]

    async def get_by_app_key(self, app_key: str) -> MobileAppConfigDomain | None:
        stmt = select(self.model).where(self.model.app_key == app_key)
        res = await self.session.execute(stmt)
        row = res.scalar_one_or_none()
        return self.to_domain(row) if row else None

    async def update_config(self, app_key: str, updates: dict[str, Any]) -> MobileAppConfigDomain | None:
        now = datetime.now(timezone.utc)
        clean = {k: v for k, v in updates.items() if v is not None}
        clean["updated_at"] = now

        stmt = (
            update(self.model)
            .where(self.model.app_key == app_key)
            .values(**clean)
            .returning(self.model)
        )
        res = await self.session.execute(stmt)
        row = res.scalar_one_or_none()
        return self.to_domain(row) if row else None

