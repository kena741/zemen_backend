"""Unit tests for AdminAuthService."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.auth.hashing import hash_password
from app.core.services.admin.auth_service import AdminAuthService
from app.domain.auth import AdminUserDomain
from app.persistence.sqlalchemy.models.users import User


@pytest.mark.asyncio
async def test_authenticate_admin_success():
    admin_id = uuid4()
    user_id = uuid4()
    now = datetime.now(timezone.utc)
    raw_password = "adminpassword123"

    user_entity = User(
        id=user_id,
        email="admin@lolelink.com",
        hashed_password=hash_password(raw_password),
        is_active=True,
    )
    admin_domain = AdminUserDomain(
        id=admin_id,
        user_id=user_id,
        email="admin@lolelink.com",
        full_name="Admin User",
        role="super_admin",
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    user_repo = MagicMock()
    user_repo.get_by_email = AsyncMock(return_value=(admin_domain, user_entity))
    user_repo.session = MagicMock()
    user_repo.session.add = MagicMock()
    user_repo.session.flush = AsyncMock()

    role_repo = MagicMock()

    service = AdminAuthService(user_repo, role_repo)
    result = await service.authenticate_admin("admin@lolelink.com", raw_password)

    assert result.admin.id == admin_id
    assert result.access_token is not None
    assert result.refresh_token is not None
    user_repo.session.add.assert_called_once()


@pytest.mark.asyncio
async def test_authenticate_admin_disabled_fails():
    admin_id = uuid4()
    user_id = uuid4()
    now = datetime.now(timezone.utc)

    user_entity = User(
        id=user_id,
        email="disabled@lolelink.com",
        hashed_password=hash_password("password123"),
        is_active=False,
    )
    admin_domain = AdminUserDomain(
        id=admin_id,
        user_id=user_id,
        email="disabled@lolelink.com",
        full_name="Disabled Admin",
        role="viewer",
        is_active=False,
        created_at=now,
        updated_at=now,
    )

    user_repo = MagicMock()
    user_repo.get_by_email = AsyncMock(return_value=(admin_domain, user_entity))
    role_repo = MagicMock()

    service = AdminAuthService(user_repo, role_repo)
    with pytest.raises(HTTPException) as exc:
        await service.authenticate_admin("disabled@lolelink.com", "password123")
    assert exc.value.status_code == 403
