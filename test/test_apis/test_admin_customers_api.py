"""Integration tests for Admin Customers API endpoints."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.security.admin_deps import AdminContext
from app.persistence.sqlalchemy.models.identity import Customer
from .conftest import ApiTestDbSession


@pytest.fixture
def super_admin_context() -> AdminContext:
    return AdminContext(
        admin_id=uuid4(),
        user_id=uuid4(),
        email="superadmin@lolelink.com",
        full_name="Super Admin",
        role="super_admin",
        permissions=["*"],
    )


def test_list_customers_success(api_client, super_admin_context):
    now = datetime.now(timezone.utc)
    mock_c = Customer(
        id=uuid4(),
        user_id=uuid4(),
        first_name="Derartu",
        last_name="Tulu",
        phone="+251911332211",
        email="derartu@example.com",
        active=True,
        wallet_amount=Decimal("0.0"),
        created_at=now,
        updated_at=now,
    )
    db = ApiTestDbSession(scalars_return=[mock_c])

    client = api_client(admin_context=super_admin_context, db_session=db)
    res = client.get("/api/v1/admin/customers")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 1
    assert data[0]["firstName"] == "Derartu"
    assert data[0]["phone"] == "+251911332211"


def test_resolve_booker_customer(api_client, super_admin_context):
    now = datetime.now(timezone.utc)
    mock_c = Customer(
        id=uuid4(),
        user_id=uuid4(),
        first_name="Admin",
        last_name="Booker",
        phone="+251900000000",
        email="admin-booker@lolelink.com",
        active=True,
        created_at=now,
    )
    db = ApiTestDbSession(scalar_return=mock_c)

    client = api_client(admin_context=super_admin_context, db_session=db)
    res = client.get("/api/v1/admin/customers/resolve-booker")
    assert res.status_code == 200
    assert res.json()["firstName"] == "Admin"
    assert res.json()["email"] == "admin-booker@lolelink.com"
