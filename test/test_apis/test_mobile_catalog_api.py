"""Integration tests for Mobile Catalog discovery and Provider service management endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1.routers.catalog import get_catalog_discovery_service
from app.api.v1.routers.providers import get_provider_service_management
from app.core.security.deps import AuthContext
from app.domain.catalog import CategoryDomain, ServiceDomain, SubCategoryDomain
from app.domain.content import BannerDomain
from app.domain.settings import CouponDomain


@pytest.fixture
def mock_catalog_service():
    return AsyncMock()


@pytest.fixture
def mock_provider_service_mgmt():
    return AsyncMock()


def test_list_categories(api_client, mock_catalog_service):
    cat_id = uuid4()
    mock_catalog_service.list_categories.return_value = [
        CategoryDomain(id=cat_id, category_name="Plumbing", active=True)
    ]

    client = api_client()
    client.app.dependency_overrides[get_catalog_discovery_service] = lambda: mock_catalog_service

    res = client.get("/api/v1/catalog/categories")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["categoryName"] == "Plumbing" or data[0]["category_name"] == "Plumbing"


def test_list_sub_categories(api_client, mock_catalog_service):
    cat_id = uuid4()
    subcat_id = uuid4()
    mock_catalog_service.list_subcategories.return_value = [
        SubCategoryDomain(
            id=subcat_id,
            category_id=cat_id,
            sub_category_name="Pipe Installation",
            is_free=True,
        )
    ]

    client = api_client()
    client.app.dependency_overrides[get_catalog_discovery_service] = lambda: mock_catalog_service

    res = client.get(f"/api/v1/catalog/sub-categories?categoryId={cat_id}")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["subCategoryName"] == "Pipe Installation"


def test_list_services(api_client, mock_catalog_service):
    srv_id = uuid4()
    prov_id = uuid4()
    cat_id = uuid4()
    subcat_id = uuid4()

    mock_catalog_service.list_public_services.return_value = [
        ServiceDomain(
            id=srv_id,
            provider_id=prov_id,
            service_name="Emergency Pipe Repair",
            category_id=cat_id,
            sub_category_id=subcat_id,
            price=250.0,
            approved=True,
        )
    ]

    client = api_client()
    client.app.dependency_overrides[get_catalog_discovery_service] = lambda: mock_catalog_service

    res = client.get("/api/v1/catalog/services")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["serviceName"] == "Emergency Pipe Repair"


def test_list_nearest_services(api_client, mock_catalog_service):
    srv_id = uuid4()
    prov_id = uuid4()
    cat_id = uuid4()
    subcat_id = uuid4()

    mock_catalog_service.list_nearest_services.return_value = [
        ServiceDomain(
            id=srv_id,
            provider_id=prov_id,
            service_name="Local Plumbing",
            category_id=cat_id,
            sub_category_id=subcat_id,
            price=150.0,
        )
    ]

    client = api_client()
    client.app.dependency_overrides[get_catalog_discovery_service] = lambda: mock_catalog_service

    res = client.get("/api/v1/catalog/services/nearest?lat=9.02&lng=38.74&radiusKm=25")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["serviceName"] == "Local Plumbing"


def test_like_service(api_client, mock_catalog_service):
    user_id = uuid4()
    srv_id = uuid4()
    prov_id = uuid4()

    mock_catalog_service.toggle_like_service.return_value = ServiceDomain(
        id=srv_id,
        provider_id=prov_id,
        service_name="Local Plumbing",
        category_id=uuid4(),
        sub_category_id=uuid4(),
        price=150.0,
        liked_user=[str(user_id)],
    )

    ctx = AuthContext(
        user_id=user_id,
        email="user@example.com",
        roles=["customer"],
    )
    client = api_client(auth_context=ctx)
    client.app.dependency_overrides[get_catalog_discovery_service] = lambda: mock_catalog_service

    res = client.put(f"/api/v1/catalog/services/{srv_id}/like")
    assert res.status_code == 200
    data = res.json()
    assert str(user_id) in data["likedUser"]


def test_banners_and_coupons(api_client, mock_catalog_service):
    mock_catalog_service.list_banners.return_value = [
        BannerDomain(id=1, banner_name="Holiday Sale", image="http://img.png", active=True)
    ]
    mock_catalog_service.get_coupon_by_code.return_value = CouponDomain(
        id=1,
        title="Holiday Promo",
        code="HOLIDAY10",
        amount=10.0,
        active=True,
    )

    client = api_client()
    client.app.dependency_overrides[get_catalog_discovery_service] = lambda: mock_catalog_service

    res_b = client.get("/api/v1/catalog/banners")
    assert res_b.status_code == 200
    assert len(res_b.json()) == 1

    res_c = client.get("/api/v1/catalog/coupons/by-code/HOLIDAY10")
    assert res_c.status_code == 200
    assert res_c.json()["code"] == "HOLIDAY10"


def test_provider_services_crud(api_client, mock_provider_service_mgmt):
    prov_id = uuid4()
    srv_id = uuid4()
    cat_id = uuid4()
    subcat_id = uuid4()

    mock_provider_service_mgmt.list_provider_services.return_value = [
        ServiceDomain(
            id=srv_id,
            provider_id=prov_id,
            service_name="Electrical Wiring",
            category_id=cat_id,
            sub_category_id=subcat_id,
            price=300.0,
        )
    ]
    mock_provider_service_mgmt.create_service.return_value = ServiceDomain(
        id=srv_id,
        provider_id=prov_id,
        service_name="New Wiring Service",
        category_id=cat_id,
        sub_category_id=subcat_id,
        price=350.0,
    )

    ctx = AuthContext(
        user_id=uuid4(),
        email="provider@example.com",
        roles=["provider"],
        provider_id=prov_id,
    )
    client = api_client(auth_context=ctx)
    client.app.dependency_overrides[get_provider_service_management] = (
        lambda: mock_provider_service_mgmt
    )

    # List provider services
    res = client.get("/api/v1/providers/me/services")
    assert res.status_code == 200
    assert len(res.json()) == 1

    # Create service
    payload = {
        "serviceName": "New Wiring Service",
        "categoryId": str(cat_id),
        "subCategoryId": str(subcat_id),
        "price": 350.0,
    }
    res_create = client.post("/api/v1/providers/me/services", json=payload)
    assert res_create.status_code == 201
    assert res_create.json()["serviceName"] == "New Wiring Service"

    # Delete service
    res_del = client.delete(f"/api/v1/providers/me/services/{srv_id}")
    assert res_del.status_code == 204
    mock_provider_service_mgmt.delete_service.assert_awaited_once_with(
        provider_id=prov_id, service_id=srv_id
    )
