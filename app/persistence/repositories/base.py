"""Generic base repository for SQLAlchemy 2.0 async persistence."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar
from uuid import uuid4

from sqlalchemy import Uuid, delete, func, inspect as sa_inspect, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.base import Base

ModelT = TypeVar("ModelT", bound=Base)
DomainT = TypeVar("DomainT")


class BaseRepository(Generic[ModelT, DomainT]):
    """Generic async repository providing standard CRUD operations."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def to_domain(self, entity: ModelT) -> DomainT:
        """Map an ORM entity to a clean domain model."""
        raise NotImplementedError

    def to_model(self, domain: DomainT) -> ModelT:
        """Map a domain entity to an ORM model."""
        raise NotImplementedError

    async def get_by_id(self, id: Any) -> DomainT | None:
        """Retrieve a single entity by its primary key."""
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)  # type: ignore[attr-defined]
        )
        entity = result.scalar_one_or_none()
        return self.to_domain(entity) if entity is not None else None

    async def list(
        self,
        offset: int = 0,
        limit: int = 50,
        filters: Sequence[Any] | None = None,
        order_by: Sequence[Any] | None = None,
    ) -> list[DomainT]:
        """List entities with filtering, ordering, and pagination."""
        stmt = select(self.model)
        if filters:
            stmt = stmt.where(*filters)
        if order_by is not None:
            stmt = stmt.order_by(*order_by)
        stmt = stmt.offset(offset).limit(limit)

        result = await self.session.execute(stmt)
        entities = result.scalars().all()
        return [self.to_domain(e) for e in entities]

    async def count(self, filters: Sequence[Any] | None = None) -> int:
        """Count total matching records."""
        stmt = select(func.count()).select_from(self.model)
        if filters:
            stmt = stmt.where(*filters)
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def exists(self, id: Any) -> bool:
        """Check if a record with the given ID exists."""
        stmt = select(1).select_from(self.model).where(self.model.id == id)  # type: ignore[attr-defined]
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def create(self, model_entity: ModelT) -> DomainT:
        """Persist a new entity to database and return its domain representation."""
        if hasattr(model_entity, "id") and getattr(model_entity, "id", None) is None:
            try:
                mapper = sa_inspect(model_entity.__class__)
                id_col = mapper.columns.get("id")
                if id_col is not None and isinstance(id_col.type, Uuid):
                    model_entity.id = uuid4()
            except Exception:
                pass

        now = datetime.now(timezone.utc)
        if hasattr(model_entity, "created_at") and getattr(model_entity, "created_at", None) is None:
            model_entity.created_at = now
        if hasattr(model_entity, "updated_at") and getattr(model_entity, "updated_at", None) is None:
            model_entity.updated_at = now

        self.session.add(model_entity)
        await self.session.flush()
        return self.to_domain(model_entity)

    async def update(self, id: Any, values: dict[str, Any]) -> DomainT | None:
        """Update fields on an existing record by ID and return updated domain model."""
        if not values:
            return await self.get_by_id(id)

        stmt = (
            update(self.model)
            .where(self.model.id == id)  # type: ignore[attr-defined]
            .values(**values)
            .returning(self.model)
        )
        result = await self.session.execute(stmt)
        updated = result.scalar_one_or_none()
        return self.to_domain(updated) if updated is not None else None

    async def delete(self, id: Any) -> bool:
        """Delete an entity by its primary key."""
        stmt = delete(self.model).where(self.model.id == id)  # type: ignore[attr-defined]
        result = await self.session.execute(stmt)
        return bool(result.rowcount and result.rowcount > 0)
