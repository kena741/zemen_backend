"""Repository for Languages."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.domain.settings import LanguageDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.config import Language


class LanguageRepository(BaseRepository[Language, LanguageDomain]):
    model = Language

    def to_domain(self, entity: Language) -> LanguageDomain:
        return LanguageDomain(
            id=entity.id,
            code=entity.code,
            name=entity.name,
            active=entity.active if entity.active is not None else True,
        )

    async def list_languages(self) -> list[LanguageDomain]:
        stmt = select(self.model).order_by(self.model.name.asc())
        res = await self.session.execute(stmt)
        return [self.to_domain(r) for r in res.scalars().all()]

    async def upsert_language(
        self,
        id: UUID | None,
        code: str,
        name: str,
        active: bool = True,
    ) -> LanguageDomain:
        lang_id = id or uuid4()
        stmt = (
            insert(self.model)
            .values(id=lang_id, code=code, name=name, active=active)
            .on_conflict_do_update(
                index_elements=[self.model.id],
                set_={"code": code, "name": name, "active": active},
            )
            .returning(self.model)
        )
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()
        if entity is None:
            return LanguageDomain(id=lang_id, code=code, name=name, active=active)
        return self.to_domain(entity)

    async def delete_language(self, lang_id: UUID) -> bool:
        stmt = delete(self.model).where(self.model.id == lang_id)
        res = await self.session.execute(stmt)
        return bool(res.rowcount and res.rowcount > 0)

    async def delete_languages(self, ids: list[UUID]) -> int:
        if not ids:
            return 0
        stmt = delete(self.model).where(self.model.id.in_(ids))
        res = await self.session.execute(stmt)
        return int(res.rowcount or 0)

