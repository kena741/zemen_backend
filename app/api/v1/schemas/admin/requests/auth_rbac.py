"""Request validation models for Admin Auth, RBAC, and Activity Logging."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AdminLoginRequest(BaseModel):
    """Payload for admin password authentication."""

    email: EmailStr
    password: str = Field(min_length=1)


class CreateRoleRequest(BaseModel):
    """Payload for creating a custom admin role."""

    slug: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] = Field(min_length=1)


class UpdateRoleRequest(BaseModel):
    """Payload for updating an existing admin role."""

    id: UUID | None = None
    slug: str | None = Field(default=None, min_length=2, max_length=50)
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] | None = None


class DeleteRoleRequest(BaseModel):
    """Payload when deleting a role via body ID."""

    id: UUID


class CreateAdminRequest(BaseModel):
    """Payload for provisioning a new admin user."""

    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str = Field(min_length=2, max_length=150)
    role: str = Field(min_length=2, max_length=50)
    is_active: bool = True


class UpdateAdminRequest(BaseModel):
    """Payload for updating admin profile or resetting password."""

    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    role: str | None = Field(default=None, min_length=2, max_length=50)
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=6)


class ActivityLogCreateRequest(BaseModel):
    """Manual activity log entry submission."""

    action: str = Field(min_length=2, max_length=50)
    resource_type: str = Field(min_length=2, max_length=50)
    resource_id: str | None = None
    route: str | None = None
    summary: str = Field(min_length=2, max_length=255)
    metadata: dict[str, Any] = Field(default_factory=dict)
    env: str = "prod"
