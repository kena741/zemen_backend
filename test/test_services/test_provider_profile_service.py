"""Unit tests for ProviderProfileService business logic and company management."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.services.provider_profile_service import ProviderProfileService
from app.domain.exceptions import EntityNotFoundError
from app.domain.provider import CompanyDomain, ProviderDomain


@pytest.fixture
def mock_repos():
    provider_repo = AsyncMock()
    company_repo = AsyncMock()
    return provider_repo, company_repo


@pytest.fixture
def provider_service(mock_repos):
    provider_repo, company_repo = mock_repos
    return ProviderProfileService(provider_repo, company_repo)


@pytest.mark.asyncio
async def test_get_provider_profile_success(provider_service, mock_repos):
    provider_repo, _ = mock_repos
    prov_id = uuid4()
    provider_repo.get_by_id.return_value = ProviderDomain(
        id=prov_id,
        user_id=uuid4(),
        first_name="Dawit",
        last_name="Kebede",
        phone_number="+251911333333",
    )

    profile = await provider_service.get_profile(prov_id)
    assert profile.id == prov_id
    assert profile.full_name == "Dawit Kebede"


@pytest.mark.asyncio
async def test_resolve_provider_id_success(provider_service, mock_repos):
    provider_repo, _ = mock_repos
    user_id = uuid4()
    prov_id = uuid4()
    provider_repo.get_by_user_id.return_value = ProviderDomain(
        id=prov_id,
        user_id=user_id,
        first_name="Dawit",
    )

    resolved = await provider_service.resolve_provider_id(user_id)
    assert resolved == prov_id


@pytest.mark.asyncio
async def test_upsert_company_success(provider_service, mock_repos):
    _, company_repo = mock_repos
    prov_id = uuid4()
    company_repo.upsert_company.return_value = CompanyDomain(
        id=uuid4(),
        provider_id=prov_id,
        name="Dawit Plumbing LLC",
        website="https://dawitplumbing.com",
    )

    res = await provider_service.upsert_company(prov_id, {"name": "Dawit Plumbing LLC"})
    assert res.provider_id == prov_id
    assert res.name == "Dawit Plumbing LLC"

