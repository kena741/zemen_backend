"""Service managing Admin User provisioning and accounts."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete as sa_delete, select

from app.core.auth.hashing import hash_password
from app.core.security.admin_deps import AdminContext
from app.core.services.admin.audit_service import AdminAuditService
from app.domain.auth import AdminUserDomain
from app.persistence.repositories.admin_role_repo import AdminRoleRepository
from app.persistence.repositories.admin_user_repo import AdminUserRepository
from app.persistence.sqlalchemy.models.admin import Admin
from app.persistence.sqlalchemy.models.users import User


class AdminUserService:
    """Handles admin users CRUD, provisioning, and password updates."""

    def __init__(
        self,
        user_repo: AdminUserRepository,
        role_repo: AdminRoleRepository,
        audit_service: AdminAuditService,
    ) -> None:
        self.user_repo = user_repo
        self.role_repo = role_repo
        self.audit_service = audit_service

    async def list_admins(self) -> list[AdminUserDomain]:
        """Fetch all admins ordered by created_at DESC."""
        return await self.user_repo.list_admins_ordered()

    async def get_admin(self, admin_id: UUID) -> AdminUserDomain:
        """Fetch single admin by ID with email."""
        admin = await self.user_repo.get_admin_with_email(admin_id)
        if not admin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")
        return admin

    async def create_admin(
        self,
        email: str,
        password: str,
        full_name: str,
        role: str,
        is_active: bool = True,
        ctx: AdminContext | None = None,
    ) -> AdminUserDomain:
        """Provision a new admin account (User + Admin entities)."""
        clean_email = email.strip().lower()
        if len(password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 6 characters long",
            )

        # Verify role exists
        role_record = await self.role_repo.get_by_slug(role)
        if not role_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Admin role '{role}' does not exist",
            )

        # Check existing user
        existing_user = (
            await self.user_repo.session.execute(
                select(User).where(User.email == clean_email)
            )
        ).scalar_one_or_none()

        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email '{clean_email}' already exists",
            )

        # Create user account
        user = User(
            email=clean_email,
            hashed_password=hash_password(password),
            is_active=is_active,
        )
        self.user_repo.session.add(user)
        await self.user_repo.session.flush()

        # Create admin profile
        admin_domain = await self.user_repo.create_admin(
            user_id=user.id,
            full_name=full_name.strip(),
            role=role,
            is_active=is_active,
            email=clean_email,
        )

        await self.audit_service.log_action(
            action="create",
            resource_type="admin",
            resource_id=str(admin_domain.id),
            summary=f"Created admin user '{admin_domain.full_name}' ({clean_email}) with role '{role}'",
            ctx=ctx,
            metadata={"email": clean_email, "role": role},
        )
        return admin_domain

    async def update_admin(
        self,
        admin_id: UUID,
        full_name: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        password: str | None = None,
        ctx: AdminContext | None = None,
    ) -> AdminUserDomain:
        """Update admin profile and optionally reset password."""
        admin = await self.get_admin(admin_id)
        update_values: dict = {}

        if full_name is not None and full_name.strip():
            update_values["full_name"] = full_name.strip()

        if role is not None and role != admin.role:
            role_record = await self.role_repo.get_by_slug(role)
            if not role_record:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Admin role '{role}' does not exist",
                )
            update_values["role"] = role

        if is_active is not None:
            update_values["is_active"] = is_active

        # Update Admin table
        if update_values:
            await self.user_repo.update(admin_id, update_values)

        # Update User password if requested
        if password is not None:
            if len(password) < 6:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Password must be at least 6 characters long",
                )
            user = await self.user_repo.session.get(User, admin.user_id)
            if user:
                user.hashed_password = hash_password(password)

        updated_domain = await self.get_admin(admin_id)

        await self.audit_service.log_action(
            action="update",
            resource_type="admin",
            resource_id=str(admin_id),
            summary=f"Updated admin user '{updated_domain.full_name}'",
            ctx=ctx,
            metadata={"changed": list(update_values.keys()) + (["password"] if password else [])},
        )
        return updated_domain

    async def delete_admin(self, admin_id: UUID, ctx: AdminContext | None = None) -> bool:
        """Delete admin profile and associated user account."""
        admin = await self.get_admin(admin_id)
        if ctx and ctx.admin_id == admin_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own admin account",
            )

        # Delete Admin row
        await self.user_repo.delete(admin_id)

        # Delete User row
        await self.user_repo.session.execute(
            sa_delete(User).where(User.id == admin.user_id)
        )

        await self.audit_service.log_action(
            action="delete",
            resource_type="admin",
            resource_id=str(admin_id),
            summary=f"Deleted admin user '{admin.full_name}' ({admin.email})",
            ctx=ctx,
            metadata={"email": admin.email, "role": admin.role},
        )
        return True
