"""Internal domain models for Admin Authentication and RBAC."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class AdminRoleDomain:
    """Domain model representing an admin RBAC role."""

    id: UUID
    slug: str
    name: str
    description: str | None
    permissions: list[str]
    is_system: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class AdminUserDomain:
    """Domain model representing an admin user account."""

    id: UUID
    user_id: UUID
    email: str | None
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
