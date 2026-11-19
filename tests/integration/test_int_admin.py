"""
Integration tests: Admin endpoints (/api/v1/admin/*).

Covers:
  - Admin Auth: GET /admin/auth/me, POST /admin/auth/login
  - RBAC Roles: GET /admin/roles, POST /admin/roles
  - RBAC Users: GET /admin/admins, POST /admin/admins
  - Audit Logs: GET /admin/activity-logs, POST /admin/activity-logs
  - Operations: GET /admin/customers, GET /admin/providers, GET /admin/bookings
"""

from datetime import datetime, timezone
import secrets
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models.admin import Admin, AdminRole


# ---------------------------------------------------------------------------
# Admin Authentication
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_me_unauthenticated_401(client: AsyncClient):
    resp = await client.get("/api/v1/admin/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_me_customer_denied_403(customer_client):
    client, _ = customer_client
    resp = await client.get("/api/v1/admin/auth/me")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_me_authenticated_200(admin_client):
    client, admin = admin_client
    resp = await client.get("/api/v1/admin/auth/me")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["adminId"] == str(admin.id)
    assert data["role"] == "superadmin"
    assert "*" in data["permissions"]


@pytest.mark.asyncio
async def test_admin_login_success(client: AsyncClient, seed_user, db_session: AsyncSession):
    now = datetime.now(timezone.utc)
    test_email = f"admin_login_{secrets.token_hex(4)}@example.com"
    user_id, plain_pw = await seed_user(email=test_email, password="AdminSecret123!")

    # Ensure role exists
    role = AdminRole(
        id=uuid4(),
        slug="ops_admin",
        name="Operations Admin",
        permissions=["*"],
        is_system=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(role)
    await db_session.flush()

    admin = Admin(
        id=uuid4(),
        user_id=user_id,
        full_name="Operations Lead",
        role="ops_admin",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(admin)
    await db_session.flush()

    login_resp = await client.post(
        "/api/v1/admin/auth/login",
        json={"email": test_email, "password": "AdminSecret123!"},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()["data"]
    assert data["admin"]["email"] == test_email
    assert "access_token" in data["session"]


@pytest.mark.asyncio
async def test_admin_login_wrong_password_401(client: AsyncClient, seed_user, db_session: AsyncSession):
    now = datetime.now(timezone.utc)
    test_email = f"admin_wrong_{secrets.token_hex(4)}@example.com"
    user_id, _ = await seed_user(email=test_email, password="CorrectPassword1!")
    admin = Admin(id=uuid4(), user_id=user_id, full_name="Admin", role="superadmin", is_active=True, created_at=now, updated_at=now)
    db_session.add(admin)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/admin/auth/login",
        json={"email": test_email, "password": "WrongPassword999!"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# RBAC Roles & Admins
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_and_create_admin_roles(admin_client):
    client, _ = admin_client

    # 1. List roles
    resp = await client.get("/api/v1/admin/roles")
    assert resp.status_code == 200
    roles = resp.json()["data"]
    assert len(roles) >= 1

    # 2. Create new role
    role_slug = f"support_lead_{secrets.token_hex(4)}"
    create_resp = await client.post(
        "/api/v1/admin/roles",
        json={
            "slug": role_slug,
            "name": "Customer Support Lead",
            "description": "Can manage tickets and view customers",
            "permissions": ["customers:read", "bookings:read"],
        },
    )
    assert create_resp.status_code == 201
    created_role = create_resp.json()["data"]
    assert created_role["slug"] == role_slug
    assert "customers:read" in created_role["permissions"]


@pytest.mark.asyncio
async def test_list_and_create_admin_users(admin_client, seed_user):
    client, _ = admin_client

    # 1. List admin accounts
    resp = await client.get("/api/v1/admin/admins")
    assert resp.status_code == 200
    users = resp.json()["data"]
    assert len(users) >= 1

    # 2. Create new admin account
    new_email = f"new_admin_{secrets.token_hex(4)}@example.com"
    create_resp = await client.post(
        "/api/v1/admin/admins",
        json={
            "email": new_email,
            "full_name": "New Sub Admin",
            "role": "superadmin",
            "password": "TempAdminPass123!",
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()["data"]
    assert created["email"] == new_email
    assert created["fullName"] == "New Sub Admin"


# ---------------------------------------------------------------------------
# Activity & Audit Logs
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_audit_logs_create_and_list(admin_client):
    client, admin = admin_client

    # 1. Create audit log
    post_resp = await client.post(
        "/api/v1/admin/activity-logs",
        json={
            "action": "CONFIG_UPDATE",
            "resource_type": "setting",
            "resource_id": "payment",
            "summary": "Updated payment gateway settings",
            "metadata": {"changed_field": "currency"},
        },
    )
    assert post_resp.status_code == 200

    # 2. List audit logs
    list_resp = await client.get("/api/v1/admin/activity-logs")
    assert list_resp.status_code == 200
    logs = list_resp.json()["data"]
    assert len(logs) >= 1
    actions = [l["action"] for l in logs]
    assert "CONFIG_UPDATE" in actions


# ---------------------------------------------------------------------------
# Admin Operational Reads: Customers, Providers, Bookings
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_list_customers(admin_client, seed_customer):
    client, _ = admin_client
    cust, _, _, _ = await seed_customer()

    resp = await client.get("/api/v1/admin/customers")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert len(items) >= 1
    ids = [c["id"] for c in items]
    assert str(cust.id) in ids


@pytest.mark.asyncio
async def test_admin_list_providers(admin_client, seed_provider):
    client, _ = admin_client
    prov, _, _, _ = await seed_provider()

    resp = await client.get("/api/v1/admin/providers")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert len(items) >= 1
    ids = [p["id"] for p in items]
    assert str(prov.id) in ids


@pytest.mark.asyncio
async def test_admin_list_bookings(admin_client, seed_booking):
    client, _ = admin_client
    bk = await seed_booking(status="pending")

    resp = await client.get("/api/v1/admin/bookings")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert len(items) >= 1
    ids = [b["id"] for b in items]
    assert str(bk.id) in ids
