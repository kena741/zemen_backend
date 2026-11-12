"""Repository for Admin user persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update

from app.domain.auth import AdminUserDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.admin import Admin
from app.persistence.sqlalchemy.models.users import User


class AdminUserRepository(BaseRepository[Admin, AdminUserDomain]):
    """SQLAlchemy repository for admin users."""

    model = Admin

    def to_domain(self, entity: Admin, email: str | None = None) -> AdminUserDomain:
        return AdminUserDomain(
            id=entity.id,
            user_id=entity.user_id,
            email=email,
            full_name=entity.full_name,
            role=entity.role,
            is_active=entity.is_active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def get_admin_with_email(self, admin_id: UUID) -> AdminUserDomain | None:
        """Fetch admin by ID joined with users.email."""
        stmt = (
            select(Admin, User.email)
            .outerjoin(User, Admin.user_id == User.id)
            .where(Admin.id == admin_id)
        )
        res = await self.session.execute(stmt)
        row = res.first()
        if not row:
            return None
        admin_entity, email = row
        return self.to_domain(admin_entity, email=email)

    async def get_by_user_id(self, user_id: UUID) -> AdminUserDomain | None:
        """Fetch admin by linked user_id."""
        stmt = (
            select(Admin, User.email)
            .outerjoin(User, Admin.user_id == User.id)
            .where(Admin.user_id == user_id)
        )
        res = await self.session.execute(stmt)
        row = res.first()
        if not row:
            return None
        admin_entity, email = row
        return self.to_domain(admin_entity, email=email)

    async def get_by_email(self, email: str) -> tuple[AdminUserDomain, User] | None:
        """Fetch admin and user entity by email for login verification."""
        clean_email = email.strip().lower()
        stmt = (
            select(Admin, User)
            .join(User, Admin.user_id == User.id)
            .where(func.lower(User.email) == clean_email)
        )
        res = await self.session.execute(stmt)
        row = res.first()
        if not row:
            return None
        admin_entity, user_entity = row
        return self.to_domain(admin_entity, email=user_entity.email), user_entity

    async def list_admins_ordered(self) -> list[AdminUserDomain]:
        """Fetch all admins ordered by created_at DESC with email."""
        stmt = (
            select(Admin, User.email)
            .outerjoin(User, Admin.user_id == User.id)
            .order_by(Admin.created_at.desc())
        )
        res = await self.session.execute(stmt)
        rows = res.all()
        return [self.to_domain(admin_e, email=email) for admin_e, email in rows]

    async def count_by_role(self, role_slug: str) -> int:
        """Count how many admin accounts are assigned to a role."""
        stmt = select(func.count()).select_from(Admin).where(Admin.role == role_slug)
        res = await self.session.execute(stmt)
        return int(res.scalar_one() or 0)

    async def create_admin(
        self,
        user_id: UUID,
        full_name: str,
        role: str,
        is_active: bool = True,
        email: str | None = None,
    ) -> AdminUserDomain:
        """Create a new Admin row linked to an existing user."""
        now = datetime.now(timezone.utc)
        admin = Admin(
            id=uuid4(),
            user_id=user_id,
            full_name=full_name,
            role=role,
            is_active=is_active,
            created_at=now,
            updated_at=now,
        )
        self.session.add(admin)
        await self.session.flush()
        return self.to_domain(admin, email=email)
