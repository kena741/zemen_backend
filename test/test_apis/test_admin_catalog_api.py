"""Integration tests for Admin Catalog and Services API endpoints."""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.security.admin_deps import AdminContext
from app.persistence.sqlalchemy.models.catalog import Category, SubCategory
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


def test_list_categories_success(api_client, super_admin_context):
    cat_id = uuid4()
    mock_c = Category(
        id=cat_id,
        category_name="Electrical",
        active=True,
    )
    db = ApiTestDbSession(scalars_return=[mock_c])

    client = api_client(admin_context=super_admin_context, db_session=db)
    res = client.get("/api/v1/admin/categories")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 1
    assert data[0]["categoryName"] == "Electrical"


def test_create_category_success(api_client, super_admin_context):
    db = ApiTestDbSession()

    client = api_client(admin_context=super_admin_context, db_session=db)
    res = client.post(
        "/api/v1/admin/categories",
        json={
            "categoryName": "Gardening",
            "active": True,
            "description": "Lawn care and landscape",
        },
    )
    assert res.status_code == 201
    assert res.json()["data"]["categoryName"] == "Gardening"


def test_approve_service_by_id(api_client, super_admin_context):
    srv_id = uuid4()
    db = ApiTestDbSession(scalar_return=srv_id)

    client = api_client(admin_context=super_admin_context, db_session=db)
    res = client.post(f"/api/v1/admin/services/{srv_id}/approve")
    assert res.status_code == 200
    assert res.json()["count"] == 1


def test_decide_featured_status(api_client, super_admin_context):
    srv_id = uuid4()
    db = ApiTestDbSession(scalar_return=srv_id)

    client = api_client(admin_context=super_admin_context, db_session=db)
    res = client.post(
        f"/api/v1/admin/services/{srv_id}/featured",
        json={"decision": "accept"},
    )
    assert res.status_code == 200
    assert res.json()["count"] == 1

