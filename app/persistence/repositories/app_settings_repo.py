"""Repository for Platform App Settings."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.domain.settings import AppSettingDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.config import AppSetting


class AppSettingsRepository(BaseRepository[AppSetting, AppSettingDomain]):
    model = AppSetting

    def to_domain(self, entity: AppSetting) -> AppSettingDomain:
        return AppSettingDomain(
            id=entity.id,
            data=entity.data or {},
            updated_at=entity.updated_at,
        )

    async def list_all_settings(self) -> list[AppSettingDomain]:
        stmt = select(self.model)
        res = await self.session.execute(stmt)
        return [self.to_domain(r) for r in res.scalars().all()]

    async def get_setting_by_id(self, setting_id: str) -> AppSettingDomain | None:
        stmt = select(self.model).where(self.model.id == setting_id)
        res = await self.session.execute(stmt)
        row = res.scalar_one_or_none()
        return self.to_domain(row) if row else None

    async def upsert_setting(self, setting_id: str, data: dict[str, Any]) -> AppSettingDomain:
        now = datetime.now(timezone.utc)
        stmt = (
            insert(self.model)
            .values(id=setting_id, data=data, updated_at=now)
            .on_conflict_do_update(
                index_elements=[self.model.id],
                set_={"data": data, "updated_at": now},
            )
            .returning(self.model)
        )
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()
        if entity is None:
            # Fallback for mock sessions that don't execute returning
            return AppSettingDomain(id=setting_id, data=data, updated_at=now)
        return self.to_domain(entity)

