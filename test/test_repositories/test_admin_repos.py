"""Unit and mapping tests for Admin repositories."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.domain.auth import AdminRoleDomain, AdminUserDomain
from app.persistence.repositories.activity_log_repo import ActivityLogRepository
from app.persistence.repositories.admin_role_repo import AdminRoleRepository
from app.persistence.repositories.admin_user_repo import AdminUserRepository
from app.persistence.sqlalchemy.models.admin import Admin, AdminActivityLog, AdminRole
from .conftest import RepoMockSession


@pytest.mark.asyncio
async def test_admin_role_repo_to_domain():
    role_id = uuid4()
    now = datetime.now(timezone.utc)
    entity = AdminRole(
        id=role_id,
        slug="operations_admin",
        name="Operations Admin",
        description="Handles catalog and bookings",
        permissions=["catalog:*", "bookings:*"],
        is_system=True,
        created_at=now,
        updated_at=now,
    )

    session = RepoMockSession(scalar_one_or_none_value=entity)
    repo = AdminRoleRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(entity)
    assert domain.id == role_id
    assert domain.slug == "operations_admin"
    assert domain.is_system is True
    assert domain.permissions == ["catalog:*", "bookings:*"]

    by_slug = await repo.get_by_slug("operations_admin")
    assert by_slug is not None
    assert by_slug.slug == "operations_admin"


@pytest.mark.asyncio
async def test_admin_user_repo_mapping():
    admin_id = uuid4()
    user_id = uuid4()
    now = datetime.now(timezone.utc)
    admin_entity = Admin(
        id=admin_id,
        user_id=user_id,
        full_name="Jane Admin",
        role="super_admin",
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    session = RepoMockSession(scalar_one_or_none_value=admin_entity)
    repo = AdminUserRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(admin_entity, email="jane@lolelink.com")
    assert domain.id == admin_id
    assert domain.user_id == user_id
    assert domain.email == "jane@lolelink.com"
    assert domain.role == "super_admin"
    assert domain.is_active is True


@pytest.mark.asyncio
async def test_activity_log_repo_create():
    now = datetime.now(timezone.utc)
    log_id = uuid4()
    log_entity = AdminActivityLog(
        id=log_id,
        action="update",
        resource_type="role",
        resource_id="operations_admin",
        route="/api/v1/admin/roles",
        summary="Updated operations_admin permissions",
        admin_id=uuid4(),
        admin_email="admin@lolelink.com",
        admin_name="Admin",
        admin_role="super_admin",
        metadata_={"diff": {"added": ["finance:read"]}},
        env="test",
        created_at=now,
    )

    session = RepoMockSession(scalar_one_or_none_value=log_entity)
    repo = ActivityLogRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(log_entity)
    assert domain.id == log_id
    assert domain.action == "update"
    assert domain.metadata["diff"]["added"] == ["finance:read"]
