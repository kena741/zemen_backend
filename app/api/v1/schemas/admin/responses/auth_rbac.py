"""Response serialization models for Admin Auth, RBAC, and Activity Logging."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AppResponseBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AdminMeData(AppResponseBase):
    admin_id: UUID = Field(serialization_alias="adminId")
    user_id: UUID = Field(serialization_alias="userId")
    email: str | None = None
    full_name: str | None = Field(default=None, serialization_alias="fullName")
    role: str
    permissions: list[str]


class AdminMeResponse(AppResponseBase):
    data: AdminMeData


class AdminTokenData(AppResponseBase):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AdminLoginData(AppResponseBase):
    admin: AdminMeData
    session: AdminTokenData


class AdminLoginResponse(AppResponseBase):
    data: AdminLoginData


class AdminRoleResponseItem(AppResponseBase):
    id: UUID
    slug: str
    name: str
    description: str | None = None
    permissions: list[str]
    is_system: bool = Field(serialization_alias="isSystem")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class AdminRolesListResponse(AppResponseBase):
    data: list[AdminRoleResponseItem]


class AdminRoleSingleResponse(AppResponseBase):
    data: AdminRoleResponseItem


class AdminUserResponseItem(AppResponseBase):
    id: UUID
    user_id: UUID = Field(serialization_alias="userId")
    email: str | None = None
    full_name: str | None = Field(default=None, serialization_alias="fullName")
    role: str
    is_active: bool = Field(serialization_alias="isActive")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class AdminUsersListResponse(AppResponseBase):
    data: list[AdminUserResponseItem]


class AdminUserSingleResponse(AppResponseBase):
    data: AdminUserResponseItem


class ActivityLogResponseItem(AppResponseBase):
    id: UUID
    created_at: datetime = Field(serialization_alias="createdAt")
    admin_id: UUID | None = Field(default=None, serialization_alias="adminId")
    admin_email: str | None = Field(default=None, serialization_alias="adminEmail")
    admin_name: str | None = Field(default=None, serialization_alias="adminName")
    admin_role: str | None = Field(default=None, serialization_alias="adminRole")
    action: str
    resource_type: str = Field(serialization_alias="resourceType")
    resource_id: str | None = Field(default=None, serialization_alias="resourceId")
    route: str | None = None
    summary: str
    metadata: dict[str, Any]
    env: str


class ActivityLogListResponse(AppResponseBase):
    data: list[ActivityLogResponseItem]
    count: int


class AdminOkResponse(AppResponseBase):
    ok: bool = True
