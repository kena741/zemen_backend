"""Unit tests for ProviderServiceManagementService."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.services.provider_service_mgmt import ProviderServiceManagementService
from app.domain.catalog import ServiceDomain
from app.domain.exceptions import EntityNotFoundError, ValidationError
from app.domain.provider import ProviderDomain


@pytest.fixture
def mock_service_repo():
    return AsyncMock()


@pytest.fixture
def mock_provider_repo():
    return AsyncMock()


@pytest.fixture
def provider_service_mgmt(mock_service_repo, mock_provider_repo):
    return ProviderServiceManagementService(
        service_repo=mock_service_repo,
        provider_repo=mock_provider_repo,
    )


@pytest.mark.asyncio
async def test_list_provider_services(provider_service_mgmt, mock_service_repo):
    prov_id = uuid4()
    srv = ServiceDomain(id=uuid4(), provider_id=prov_id, service_name="Electrical", price=50.0)
    mock_service_repo.list_services.return_value = [srv]

    services = await provider_service_mgmt.list_provider_services(prov_id)
    assert len(services) == 1
    assert services[0].service_name == "Electrical"
    mock_service_repo.list_services.assert_awaited_once_with(
        include_archived=False, provider_id=prov_id
    )


@pytest.mark.asyncio
async def test_get_provider_service_unauthorized(provider_service_mgmt, mock_service_repo):
    prov_id = uuid4()
    other_prov_id = uuid4()
    srv_id = uuid4()
    mock_service_repo.get_by_id_enriched.return_value = ServiceDomain(
        id=srv_id, provider_id=other_prov_id, service_name="Other Provider Service", price=50.0
    )

    with pytest.raises(EntityNotFoundError):
        await provider_service_mgmt.get_service(prov_id, srv_id)


@pytest.mark.asyncio
async def test_create_service_without_plan_fails(
    provider_service_mgmt, mock_service_repo, mock_provider_repo
):
    prov_id = uuid4()
    mock_provider_repo.get_by_id.return_value = ProviderDomain(
        id=prov_id,
        user_id=uuid4(),
        phone_number="+251911223344",
        service_tier_max=0,  # No plan purchased yet
    )

    data = {
        "service_name": "Roof Repair",
        "category_id": uuid4(),
        "sub_category_id": uuid4(),
        "price": 500.0,
    }
    with pytest.raises(ValidationError, match="No active service plan found"):
        await provider_service_mgmt.create_service(prov_id, data)


@pytest.mark.asyncio
async def test_create_service_tier_limit_exceeded(
    provider_service_mgmt, mock_service_repo, mock_provider_repo
):
    prov_id = uuid4()
    mock_provider_repo.get_by_id.return_value = ProviderDomain(
        id=prov_id,
        user_id=uuid4(),
        phone_number="+251911223344",
        service_tier_max=3,
    )
    mock_service_repo.count_active_by_provider.return_value = 3

    data = {
        "service_name": "Roof Repair",
        "category_id": uuid4(),
        "sub_category_id": uuid4(),
        "price": 500.0,
    }
    with pytest.raises(ValidationError, match="Tier limit reached"):
        await provider_service_mgmt.create_service(prov_id, data)


@pytest.mark.asyncio
async def test_create_service_success(provider_service_mgmt, mock_service_repo, mock_provider_repo):
    prov_id = uuid4()
    mock_provider_repo.get_by_id.return_value = ProviderDomain(
        id=prov_id,
        user_id=uuid4(),
        phone_number="+251911223344",
        service_tier_max=5,
    )
    mock_service_repo.count_active_by_provider.return_value = 2
    mock_service_repo.create_service.return_value = ServiceDomain(
        id=uuid4(),
        provider_id=prov_id,
        service_name="Roof Repair",
        price=500.0,
    )

    cat_id = uuid4()
    subcat_id = uuid4()
    data = {
        "service_name": "Roof Repair",
        "category_id": cat_id,
        "sub_category_id": subcat_id,
        "price": 500.0,
        "discount": 10.0,
    }

    created = await provider_service_mgmt.create_service(prov_id, data)
    assert created.provider_id == prov_id
    assert created.service_name == "Roof Repair"
    mock_service_repo.create_service.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_service_success(provider_service_mgmt, mock_service_repo):
    prov_id = uuid4()
    srv_id = uuid4()
    mock_service_repo.get_by_id_enriched.return_value = ServiceDomain(
        id=srv_id, provider_id=prov_id, service_name="Old Title", price=100.0
    )
    updated_domain = ServiceDomain(
        id=srv_id, provider_id=prov_id, service_name="New Title", price=120.0
    )
    mock_service_repo.update_service_fields.return_value = updated_domain

    res = await provider_service_mgmt.update_service(
        prov_id, srv_id, {"service_name": "New Title", "price": 120.0}
    )
    assert res.service_name == "New Title"
    mock_service_repo.update_service_fields.assert_awaited_once_with(
        service_id=srv_id,
        provider_id=prov_id,
        patch={"service_name": "New Title", "price": 120.0},
    )
