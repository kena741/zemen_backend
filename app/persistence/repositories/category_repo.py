"""Repository for Category persistence."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, select, update

from app.domain.catalog import CategoryDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.catalog import Category


class CategoryRepository(BaseRepository[Category, CategoryDomain]):
    model = Category

    def to_domain(self, entity: Category) -> CategoryDomain:
        return CategoryDomain(
            id=entity.id,
            category_name=entity.category_name,
            image=entity.image,
            active=entity.active,
            description=entity.description,
        )

    async def list_all(self) -> list[CategoryDomain]:
        stmt = select(self.model).order_by(self.model.category_name.asc())
        res = await self.session.execute(stmt)
        return [self.to_domain(c) for c in res.scalars().all()]

    async def create_category(
        self,
        category_name: str,
        image: str | None = None,
        active: bool = True,
        description: str | None = None,
    ) -> CategoryDomain:
        entity = Category(
            id=uuid4(),
            category_name=category_name.strip(),
            image=image,
            active=active,
            description=description,
        )
        return await self.create(entity)
