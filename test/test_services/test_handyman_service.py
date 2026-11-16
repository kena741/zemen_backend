"""Unit tests for HandymanService personnel operations and isolation."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.services.handyman_service import HandymanService
from app.domain.exceptions import EntityNotFoundError
from app.domain.provider import HandymanDomain


@pytest.fixture
def mock_handyman_repo():
    return AsyncMock()


@pytest.fixture
def handyman_service(mock_handyman_repo):
    return HandymanService(mock_handyman_repo)


@pytest.mark.asyncio
async def test_list_handymen_for_provider(handyman_service, mock_handyman_repo):
    prov_id = uuid4()
    item = HandymanDomain(
        id=uuid4(),
        provider_id=prov_id,
        first_name="Gemechu",
        last_name="Bekele",
    )
    mock_handyman_repo.list_by_provider.return_value = [item]

    res = await handyman_service.list_for_provider(prov_id)
    assert len(res) == 1
    assert res[0].first_name == "Gemechu"
    mock_handyman_repo.list_by_provider.assert_called_once_with(prov_id)


@pytest.mark.asyncio
async def test_get_handyman_cross_provider_denial(handyman_service, mock_handyman_repo):
    item = HandymanDomain(
        id=uuid4(),
        provider_id=uuid4(),
        first_name="Gemechu",
    )
    mock_handyman_repo.get_by_id.return_value = item

    different_provider_id = uuid4()
    with pytest.raises(EntityNotFoundError):
        await handyman_service.get_handyman(item.id, provider_id=different_provider_id)


@pytest.mark.asyncio
async def test_delete_handyman_success(handyman_service, mock_handyman_repo):
    mock_handyman_repo.delete_handyman.return_value = True
    deleted = await handyman_service.delete_handyman(uuid4(), uuid4())
    assert deleted is True

