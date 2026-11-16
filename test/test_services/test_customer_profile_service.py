"""Unit tests for CustomerProfileService business logic and validation."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.services.customer_profile_service import CustomerProfileService
from app.domain.customer import CustomerDomain
from app.domain.exceptions import EntityConflictError, EntityNotFoundError


@pytest.fixture
def mock_customer_repo():
    return AsyncMock()


@pytest.fixture
def customer_service(mock_customer_repo):
    return CustomerProfileService(mock_customer_repo)


@pytest.mark.asyncio
async def test_get_profile_success(customer_service, mock_customer_repo):
    cust_id = uuid4()
    mock_customer_repo.get_by_id.return_value = CustomerDomain(
        id=cust_id,
        first_name="Sara",
        last_name="Tadesse",
        phone="+251911223344",
    )

    profile = await customer_service.get_profile(cust_id)
    assert profile.id == cust_id
    assert profile.full_name == "Sara Tadesse"


@pytest.mark.asyncio
async def test_get_profile_not_found(customer_service, mock_customer_repo):
    mock_customer_repo.get_by_id.return_value = None
    with pytest.raises(EntityNotFoundError):
        await customer_service.get_profile(uuid4())


@pytest.mark.asyncio
async def test_update_profile_phone_conflict(customer_service, mock_customer_repo):
    cust_id = uuid4()
    mock_customer_repo.is_phone_registered.return_value = True

    with pytest.raises(EntityConflictError):
        await customer_service.update_profile(cust_id, {"phone": "0911998877"})


@pytest.mark.asyncio
async def test_update_profile_success(customer_service, mock_customer_repo):
    cust_id = uuid4()
    mock_customer_repo.is_phone_registered.return_value = False
    mock_customer_repo.update_customer.return_value = CustomerDomain(
        id=cust_id,
        first_name="Sara",
        last_name="Updated",
        phone="+251911223344",
    )

    updated = await customer_service.update_profile(cust_id, {"last_name": "Updated"})
    assert updated.last_name == "Updated"
    mock_customer_repo.update_customer.assert_called_once()

