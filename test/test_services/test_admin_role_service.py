"""Unit tests for AdminRoleService."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.services.admin.role_service import AdminRoleService
from app.domain.auth import AdminRoleDomain


@pytest.mark.asyncio
async def test_system_role_cannot_be_deleted():
    role_id = uuid4()
    now = datetime.now(timezone.utc)
    system_role = AdminRoleDomain(
        id=role_id,
        slug="super_admin",
        name="Super Admin",
        description=None,
        permissions=["*"],
        is_system=True,
        created_at=now,
        updated_at=now,
    )

    role_repo = MagicMock()
    role_repo.get_by_id = AsyncMock(return_value=system_role)

    user_repo = MagicMock()
    audit_service = MagicMock()

    service = AdminRoleService(role_repo, user_repo, audit_service)

    with pytest.raises(HTTPException) as exc:
        await service.delete_role(role_id)
    assert exc.value.status_code == 400
    assert "System roles cannot be deleted" in exc.value.detail


@pytest.mark.asyncio
async def test_role_with_assigned_admins_cannot_be_deleted():
    role_id = uuid4()
    now = datetime.now(timezone.utc)
    custom_role = AdminRoleDomain(
        id=role_id,
        slug="moderator",
        name="Moderator",
        description=None,
        permissions=["services:read"],
        is_system=False,
        created_at=now,
        updated_at=now,
    )

    role_repo = MagicMock()
    role_repo.get_by_id = AsyncMock(return_value=custom_role)

    user_repo = MagicMock()
    user_repo.count_by_role = AsyncMock(return_value=2)  # 2 admins assigned
    audit_service = MagicMock()

    service = AdminRoleService(role_repo, user_repo, audit_service)

    with pytest.raises(HTTPException) as exc:
        await service.delete_role(role_id)
    assert exc.value.status_code == 400
    assert "admin user(s) currently assigned" in exc.value.detail
