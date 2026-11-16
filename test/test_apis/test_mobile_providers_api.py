"""Integration tests for Mobile Provider, Company, and Handymen endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1.routers.providers import (
    get_handyman_service,
    get_provider_document_service,
    get_provider_profile_service,
)
from app.core.security.deps import AuthContext
from app.domain.provider import CompanyDomain, HandymanDomain, ProviderDomain
from app.domain.verification import VerifyDocumentDomain


@pytest.fixture
def mock_provider_service():
    return AsyncMock()


@pytest.fixture
def mock_handyman_service():
    return AsyncMock()


@pytest.fixture
def mock_doc_service():
    return AsyncMock()


def test_get_provider_me(api_client, mock_provider_service):
    user_id = uuid4()
    prov_id = uuid4()
    mock_provider_service.get_profile.return_value = ProviderDomain(
        id=prov_id,
        user_id=user_id,
        first_name="Bereket",
        last_name="Solomon",
        phone_number="+251911555555",
        active=True,
    )

    ctx = AuthContext(
        user_id=user_id,
        email="bereket@example.com",
        roles=["provider"],
        provider_id=prov_id,
    )
    client = api_client(auth_context=ctx)
    client.app.dependency_overrides[get_provider_profile_service] = lambda: mock_provider_service

    res = client.get("/api/v1/providers/me")
    assert res.status_code == 200
    data = res.json()
    assert data["firstName"] == "Bereket" or data["first_name"] == "Bereket"


def test_resolve_provider_id(api_client, mock_provider_service):
    user_id = uuid4()
    prov_id = uuid4()

    ctx = AuthContext(
        user_id=user_id,
        email="bereket@example.com",
        roles=["provider"],
        provider_id=prov_id,
    )
    client = api_client(auth_context=ctx)
    client.app.dependency_overrides[get_provider_profile_service] = lambda: mock_provider_service

    res = client.get("/api/v1/providers/resolve-id")
    assert res.status_code == 200
    assert res.json()["providerId"] == str(prov_id)


def test_provider_company_upsert(api_client, mock_provider_service):
    user_id = uuid4()
    prov_id = uuid4()
    mock_provider_service.upsert_company.return_value = CompanyDomain(
        id=uuid4(),
        provider_id=prov_id,
        name="Bereket Plumbing",
        website="https://bereketplumbing.com",
    )

    ctx = AuthContext(
        user_id=user_id,
        email="bereket@example.com",
        roles=["provider"],
        provider_id=prov_id,
    )
    client = api_client(auth_context=ctx)
    client.app.dependency_overrides[get_provider_profile_service] = lambda: mock_provider_service

    res = client.post("/api/v1/providers/me/company", json={"name": "Bereket Plumbing"})
    assert res.status_code == 200
    assert res.json()["name"] == "Bereket Plumbing"


def test_handymen_crud(api_client, mock_handyman_service):
    user_id = uuid4()
    prov_id = uuid4()
    h_id = uuid4()
    item = HandymanDomain(
        id=h_id,
        provider_id=prov_id,
        first_name="Kassahun",
        last_name="Lemma",
        phone_number="+251911888888",
    )
    mock_handyman_service.list_for_provider.return_value = [item]
    mock_handyman_service.create_handyman.return_value = item

    ctx = AuthContext(
        user_id=user_id,
        email="bereket@example.com",
        roles=["provider"],
        provider_id=prov_id,
    )
    client = api_client(auth_context=ctx)
    client.app.dependency_overrides[get_handyman_service] = lambda: mock_handyman_service

    # List
    res = client.get("/api/v1/providers/me/handymen")
    assert res.status_code == 200
    assert len(res.json()) == 1

    # Create
    res2 = client.post(
        "/api/v1/providers/me/handymen",
        json={"firstName": "Kassahun", "lastName": "Lemma", "phoneNumber": "+251911888888"},
    )
    assert res2.status_code == 201
    assert res2.json()["firstName"] == "Kassahun" or res2.json()["first_name"] == "Kassahun"


def test_provider_verify_documents(api_client, mock_doc_service):
    from datetime import datetime, timezone
    user_id = uuid4()
    prov_id = uuid4()
    doc_id = uuid4()
    mock_doc_service.list_provider_documents.return_value = [
        VerifyDocumentDomain(
            id=uuid4(),
            provider_id=prov_id,
            document_id=doc_id,
            document_image="https://bucket/img.png",
            created_at=datetime.now(timezone.utc),
            is_verify=True,
        )
    ]

    ctx = AuthContext(
        user_id=user_id,
        email="bereket@example.com",
        roles=["provider"],
        provider_id=prov_id,
    )
    client = api_client(auth_context=ctx)
    client.app.dependency_overrides[get_provider_document_service] = lambda: mock_doc_service

    res = client.get("/api/v1/providers/me/documents")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["documentId"] == str(doc_id) or data[0]["document_id"] == str(doc_id)
