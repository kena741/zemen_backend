"""Unit tests for CatalogDiscoveryService."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.services.catalog_discovery_service import CatalogDiscoveryService
from app.domain.catalog import CategoryDomain, ServiceDomain, SubCategoryDomain
from app.domain.content import BannerDomain
from app.domain.exceptions import EntityNotFoundError, ValidationError
from app.domain.settings import CouponDomain


@pytest.fixture
def mock_category_repo():
    return AsyncMock()


@pytest.fixture
def mock_subcategory_repo():
    return AsyncMock()


@pytest.fixture
def mock_service_repo():
    return AsyncMock()


@pytest.fixture
def mock_banner_repo():
    return AsyncMock()


@pytest.fixture
def mock_coupon_repo():
    return AsyncMock()


@pytest.fixture
def discovery_service(
    mock_category_repo,
    mock_subcategory_repo,
    mock_service_repo,
    mock_banner_repo,
    mock_coupon_repo,
):
    return CatalogDiscoveryService(
        category_repo=mock_category_repo,
        subcategory_repo=mock_subcategory_repo,
        service_repo=mock_service_repo,
        banner_repo=mock_banner_repo,
        coupon_repo=mock_coupon_repo,
    )


@pytest.mark.asyncio
async def test_list_categories(discovery_service, mock_category_repo):
    cat = CategoryDomain(id=uuid4(), category_name="Cleaning", active=True)
    mock_category_repo.list_categories.return_value = [cat]

    results = await discovery_service.list_categories()
    assert len(results) == 1
    assert results[0].category_name == "Cleaning"
    mock_category_repo.list_categories.assert_awaited_once_with(active_only=True)


@pytest.mark.asyncio
async def test_list_subcategories(discovery_service, mock_subcategory_repo):
    cat_id = uuid4()
    subcat = SubCategoryDomain(id=uuid4(), category_id=cat_id, sub_category_name="Home Cleaning")
    mock_subcategory_repo.list_by_category_id.return_value = [subcat]

    results = await discovery_service.list_subcategories(category_id=cat_id)
    assert len(results) == 1
    assert results[0].sub_category_name == "Home Cleaning"


@pytest.mark.asyncio
async def test_get_service_success(discovery_service, mock_service_repo):
    service_id = uuid4()
    srv = ServiceDomain(
        id=service_id,
        provider_id=uuid4(),
        service_name="Deep Cleaning",
        price=150.0,
        approved=True,
        is_archived=False,
    )
    mock_service_repo.get_by_id_enriched.return_value = srv

    res = await discovery_service.get_service(service_id)
    assert res.id == service_id
    assert res.service_name == "Deep Cleaning"


@pytest.mark.asyncio
async def test_get_service_not_found_or_unapproved(discovery_service, mock_service_repo):
    mock_service_repo.get_by_id_enriched.return_value = None
    with pytest.raises(EntityNotFoundError):
        await discovery_service.get_service(uuid4())

    unapproved = ServiceDomain(
        id=uuid4(),
        provider_id=uuid4(),
        service_name="Unapproved",
        price=100.0,
        approved=False,
        is_archived=False,
    )
    mock_service_repo.get_by_id_enriched.return_value = unapproved
    with pytest.raises(EntityNotFoundError):
        await discovery_service.get_service(unapproved.id)


@pytest.mark.asyncio
async def test_toggle_like_service(discovery_service, mock_service_repo):
    service_id = uuid4()
    user_id = uuid4()
    updated = ServiceDomain(
        id=service_id,
        provider_id=uuid4(),
        service_name="Painting",
        price=200.0,
        liked_user=[str(user_id)],
    )
    mock_service_repo.toggle_like.return_value = updated

    res = await discovery_service.toggle_like_service(service_id, user_id)
    assert res.liked_user == [str(user_id)]


@pytest.mark.asyncio
async def test_list_nearest_services(discovery_service, mock_service_repo):
    # User in Addis Ababa (9.02497, 38.74689)
    # Service 1: close (~2km) (9.0300, 38.7500)
    # Service 2: far (~100km) (9.9000, 39.5000)
    s1 = ServiceDomain(
        id=uuid4(),
        provider_id=uuid4(),
        service_name="Nearby Plumber",
        price=100.0,
        position={"lat": 9.0300, "lng": 38.7500},
    )
    s2 = ServiceDomain(
        id=uuid4(),
        provider_id=uuid4(),
        service_name="Far Plumber",
        price=100.0,
        position={"lat": 9.9000, "lng": 39.5000},
    )
    mock_service_repo.list_public_services.return_value = [s2, s1]

    nearest = await discovery_service.list_nearest_services(
        lat=9.02497, lng=38.74689, radius_km=10.0
    )
    assert len(nearest) == 1
    assert nearest[0].service_name == "Nearby Plumber"


@pytest.mark.asyncio
async def test_get_coupon_by_code(discovery_service, mock_coupon_repo):
    mock_coupon_repo.get_by_code.return_value = CouponDomain(
        id=1,
        title="Save 20%",
        code="SAVE20",
        amount=20.0,
        active=True,
    )
    coupon = await discovery_service.get_coupon_by_code("SAVE20")
    assert coupon.code == "SAVE20"

    # Inactive coupon
    mock_coupon_repo.get_by_code.return_value = CouponDomain(
        id=2,
        title="Expired",
        code="EXPIRED",
        amount=10.0,
        active=False,
    )
    with pytest.raises(ValidationError):
        await discovery_service.get_coupon_by_code("EXPIRED")
