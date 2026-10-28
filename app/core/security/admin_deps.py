"""Admin (lolelink) authorization: Supabase JWT → active `admin` row → role permissions.

Mirrors `requireAdminPermission` in lolelink-admin `src/lib/admin-auth.ts`.
Admin identity comes only from the `admin` table keyed by the token subject,
never from JWT metadata or the request body.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.admin_permissions import has_permission, resolve_role_permissions
from app.core.security.deps import bearer, decode_bearer
from app.persistence.sqlalchemy.deps import get_db
from app.persistence.sqlalchemy.models import Admin, AdminRole


@dataclass
class AdminContext:
    admin_id: UUID
    user_id: UUID
    email: str | None
    full_name: str | None
    role: str
    permissions: list[str] = field(default_factory=list)
    route: str | None = None

    def can(self, permission: str) -> bool:
        return has_permission(self.permissions, permission)


async def get_admin_context(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminContext:
    user_id, email, _claims = decode_bearer(creds)

    admin = (
        await db.execute(select(Admin).where(Admin.user_id == user_id))
    ).scalar_one_or_none()
    if admin is None or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    role_row = (
        await db.execute(select(AdminRole).where(AdminRole.slug == admin.role))
    ).scalar_one_or_none()
    permissions = resolve_role_permissions(admin.role, role_row.permissions if role_row else None)

    return AdminContext(
        admin_id=admin.id,
        user_id=user_id,
        email=email,
        full_name=admin.full_name,
        role=admin.role,
        permissions=permissions,
        route=request.url.path,
    )


def require_admin_permission(permission: str):
    async def _dep(ctx: Annotated[AdminContext, Depends(get_admin_context)]) -> AdminContext:
        if not ctx.can(permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return ctx

    return _dep


RequireAdmin = Annotated[AdminContext, Depends(get_admin_context)]
