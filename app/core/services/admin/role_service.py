"""Service managing Admin RBAC Roles and permission policies."""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException, status

from app.core.security.admin_deps import AdminContext
from app.core.security.admin_permissions import apply_role_permission_policy
from app.core.services.admin.audit_service import AdminAuditService
from app.domain.auth import AdminRoleDomain
from app.persistence.repositories.admin_role_repo import AdminRoleRepository
from app.persistence.repositories.admin_user_repo import AdminUserRepository
from app.persistence.sqlalchemy.models.admin import AdminRole


def normalize_slug(slug: str) -> str:
    """Normalize a role slug to lowercase snake_case."""
    s = slug.strip().lower()
    return re.sub(r"[^a-z0-9_]+", "_", s).strip("_")


class AdminRoleService:
    """Handles admin roles CRUD and permission sanitization."""

    def __init__(
        self,
        role_repo: AdminRoleRepository,
        user_repo: AdminUserRepository,
        audit_service: AdminAuditService,
    ) -> None:
        self.role_repo = role_repo
        self.user_repo = user_repo
        self.audit_service = audit_service

    async def list_roles(self) -> list[AdminRoleDomain]:
        """List all roles ordered by name."""
        return await self.role_repo.list_ordered_by_name()

    async def get_role(self, role_id: UUID) -> AdminRoleDomain:
        """Get role by ID or raise 404."""
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
        return role

    async def create_role(
        self,
        slug: str,
        name: str,
        permissions: list[str],
        description: str | None = None,
        ctx: AdminContext | None = None,
    ) -> AdminRoleDomain:
        """Create a custom admin role."""
        clean_slug = normalize_slug(slug)
        if not clean_slug:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid slug")

        existing = await self.role_repo.get_by_slug(clean_slug)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Role with slug '{clean_slug}' already exists",
            )

        sanitized_perms = apply_role_permission_policy(clean_slug, permissions)
        if not sanitized_perms:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role must contain at least one valid permission",
            )

        entity = AdminRole(
            slug=clean_slug,
            name=name.strip(),
            description=description.strip() if description else None,
            permissions=sanitized_perms,
            is_system=False,
        )
        domain = await self.role_repo.create(entity)

        await self.audit_service.log_action(
            action="create",
            resource_type="role",
            resource_id=str(domain.id),
            summary=f"Created custom role '{domain.name}' ({domain.slug})",
            ctx=ctx,
            metadata={"slug": domain.slug, "permissions": domain.permissions},
        )
        return domain

    async def update_role(
        self,
        role_id: UUID,
        name: str | None = None,
        description: str | None = None,
        permissions: list[str] | None = None,
        slug: str | None = None,
        ctx: AdminContext | None = None,
    ) -> AdminRoleDomain:
        """Update role fields with system protection."""
        role = await self.get_role(role_id)
        update_values: dict = {}

        if slug is not None:
            clean_slug = normalize_slug(slug)
            if role.is_system and clean_slug != role.slug:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot change slug of a system role",
                )
            if clean_slug != role.slug:
                existing = await self.role_repo.get_by_slug(clean_slug)
                if existing and existing.id != role_id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Role with slug '{clean_slug}' already exists",
                    )
                update_values["slug"] = clean_slug

        if name is not None and name.strip():
            update_values["name"] = name.strip()

        if description is not None:
            update_values["description"] = description.strip() or None

        if permissions is not None:
            effective_slug = update_values.get("slug", role.slug)
            sanitized = apply_role_permission_policy(effective_slug, permissions)
            if not sanitized:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Role must have at least one permission",
                )
            update_values["permissions"] = sanitized

        updated = await self.role_repo.update(role_id, update_values)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

        await self.audit_service.log_action(
            action="update",
            resource_type="role",
            resource_id=str(role_id),
            summary=f"Updated role '{updated.name}' ({updated.slug})",
            ctx=ctx,
            metadata={"changed": list(update_values.keys())},
        )
        return updated

    async def delete_role(self, role_id: UUID, ctx: AdminContext | None = None) -> bool:
        """Delete custom role if no admins are assigned to it."""
        role = await self.get_role(role_id)
        if role.is_system:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="System roles cannot be deleted",
            )

        assigned_count = await self.user_repo.count_by_role(role.slug)
        if assigned_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete role: {assigned_count} admin user(s) currently assigned",
            )

        deleted = await self.role_repo.delete(role_id)
        if deleted:
            await self.audit_service.log_action(
                action="delete",
                resource_type="role",
                resource_id=str(role_id),
                summary=f"Deleted role '{role.name}' ({role.slug})",
                ctx=ctx,
                metadata={"slug": role.slug},
            )
        return deleted
