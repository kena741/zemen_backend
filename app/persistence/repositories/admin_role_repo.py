"""Repository for AdminRole persistence."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.domain.auth import AdminRoleDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.admin import AdminRole


class AdminRoleRepository(BaseRepository[AdminRole, AdminRoleDomain]):
    """SQLAlchemy repository for admin roles."""

    model = AdminRole

    def to_domain(self, entity: AdminRole) -> AdminRoleDomain:
        return AdminRoleDomain(
            id=entity.id,
            slug=entity.slug,
            name=entity.name,
            description=entity.description,
            permissions=list(entity.permissions),
            is_system=entity.is_system,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def to_model(self, domain: AdminRoleDomain) -> AdminRole:
        return AdminRole(
            id=domain.id,
            slug=domain.slug,
            name=domain.name,
            description=domain.description,
            permissions=domain.permissions,
            is_system=domain.is_system,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
        )

    async def get_by_slug(self, slug: str) -> AdminRoleDomain | None:
        """Fetch role by unique slug."""
        stmt = select(AdminRole).where(AdminRole.slug == slug)
        res = await self.session.execute(stmt)
        entity = res.scalar_one_or_none()
        return self.to_domain(entity) if entity is not None else None

    async def list_ordered_by_name(self) -> list[AdminRoleDomain]:
        """Fetch all roles ordered alphabetically by name."""
        stmt = select(AdminRole).order_by(AdminRole.name.asc())
        res = await self.session.execute(stmt)
        return [self.to_domain(e) for e in res.scalars().all()]
