"""API integration tests for Admin Auth, RBAC, and Activity Log endpoints."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.security.admin_deps import AdminContext
from app.domain.auth import AdminRoleDomain, AdminUserDomain
from app.persistence.sqlalchemy.models.admin import Admin, AdminActivityLog, AdminRole
from .conftest import ApiTestDbSession


def test_admin_me_success(api_client, super_admin_context):
    client = api_client(admin_context=super_admin_context)
    res = client.get("/api/v1/admin/auth/me")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["role"] == "super_admin"
    assert data["permissions"] == ["*"]


def test_admin_me_unauthenticated(api_client):
    client = api_client(admin_context=None)
    res = client.get("/api/v1/admin/auth/me")
    assert res.status_code == 401


def test_list_roles_with_permission(api_client, super_admin_context):
    now = datetime.now(timezone.utc)
    mock_role = AdminRole(
        id=uuid4(),
        slug="finance_admin",
        name="Finance Admin",
        description="Manages payouts",
        permissions=["finance:*"],
        is_system=True,
        created_at=now,
        updated_at=now,
    )
    db = ApiTestDbSession(scalars_return=[mock_role])

    client = api_client(admin_context=super_admin_context, db_session=db)
    res = client.get("/api/v1/admin/roles")
    assert res.status_code == 200
    payload = res.json()
    assert len(payload["data"]) == 1
    assert payload["data"][0]["slug"] == "finance_admin"


def test_create_role_unauthorized(api_client):
    # Viewer role has no roles:write permission
    viewer_ctx = AdminContext(
        admin_id=uuid4(),
        user_id=uuid4(),
        email="viewer@lolelink.com",
        full_name="Viewer",
        role="viewer",
        permissions=["services:read"],
    )
    client = api_client(admin_context=viewer_ctx)
    res = client.post(
        "/api/v1/admin/roles",
        json={
            "slug": "custom_manager",
            "name": "Custom Manager",
            "permissions": ["catalog:read"],
        },
    )
    assert res.status_code == 403


def test_create_role_success(api_client, super_admin_context):
    now = datetime.now(timezone.utc)
    role_id = uuid4()
    mock_created = AdminRole(
        id=role_id,
        slug="ops_lead",
        name="Ops Lead",
        description="Leads ops",
        permissions=["catalog:*"],
        is_system=False,
        created_at=now,
        updated_at=now,
    )
    # Return None for get_by_slug check, then created role
    db = ApiTestDbSession(scalar_return=None)

    client = api_client(admin_context=super_admin_context, db_session=db)
    res = client.post(
        "/api/v1/admin/roles",
        json={
            "slug": "ops_lead",
            "name": "Ops Lead",
            "description": "Leads ops",
            "permissions": ["catalog:*"],
        },
    )
    assert res.status_code == 201
    assert res.json()["data"]["slug"] == "ops_lead"


def test_list_admins_success(api_client, super_admin_context):
    now = datetime.now(timezone.utc)
    mock_admin = Admin(
        id=uuid4(),
        user_id=uuid4(),
        full_name="Admin One",
        role="super_admin",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    # The list query returns rows of (Admin, email)
    db = ApiTestDbSession(scalars_return=[(mock_admin, "admin1@lolelink.com")])

    client = api_client(admin_context=super_admin_context, db_session=db)
    res = client.get("/api/v1/admin/admins")
    assert res.status_code == 200
    assert len(res.json()["data"]) == 1
    assert res.json()["data"][0]["fullName"] == "Admin One"


def test_activity_logs_list(api_client, super_admin_context):
    now = datetime.now(timezone.utc)
    mock_log = AdminActivityLog(
        id=uuid4(),
        action="update",
        resource_type="booking",
        resource_id="123",
        summary="Updated status",
        route="/api/v1/admin/bookings/123",
        admin_id=super_admin_context.admin_id,
        admin_email=super_admin_context.email,
        admin_name=super_admin_context.full_name,
        admin_role=super_admin_context.role,
        metadata_={"old": "pending", "new": "accepted"},
        env="test",
        created_at=now,
    )
    db = ApiTestDbSession(scalar_return=1, scalars_return=[mock_log])

    client = api_client(admin_context=super_admin_context, db_session=db)
    res = client.get("/api/v1/admin/activity-logs")
    assert res.status_code == 200
    payload = res.json()
    assert payload["count"] == 1
    assert payload["data"][0]["action"] == "update"
