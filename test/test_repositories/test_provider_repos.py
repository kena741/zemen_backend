"""Unit and mapping tests for Provider and Verification repositories."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.domain.provider import BankMethodDomain, CompanyDomain, ProviderDomain
from app.domain.verification import DocumentDeliveryDomain, VerifyDocumentDomain
from app.persistence.repositories.document_delivery_repo import DocumentDeliveryRepository
from app.persistence.repositories.provider_bank_repo import ProviderBankRepository
from app.persistence.repositories.provider_company_repo import ProviderCompanyRepository
from app.persistence.repositories.provider_repo import ProviderRepository
from app.persistence.repositories.verify_document_repo import VerifyDocumentRepository
from app.persistence.sqlalchemy.models.admin import DocumentDelivery, VerifyDocument
from app.persistence.sqlalchemy.models.finance import ProviderPaymentMethod
from app.persistence.sqlalchemy.models.identity import Company, Provider
from .conftest import RepoMockSession


@pytest.mark.asyncio
async def test_provider_repo_to_domain():
    prov_id = uuid4()
    user_id = uuid4()
    now = datetime.now(timezone.utc)
    entity = Provider(
        id=prov_id,
        user_id=user_id,
        first_name="Abebe",
        last_name="Bikila",
        email="abebe@example.com",
        phone_number="+251911223344",
        active=True,
        wallet_amount="1500.00",
        activation_paid=True,
        service_tier_max=3,
        verified_subcategory_ids=[],
        created_at=now,
        updated_at=now,
    )

    session = RepoMockSession(scalar_one_or_none_value=entity)
    repo = ProviderRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(entity)
    assert domain.id == prov_id
    assert domain.full_name == "Abebe Bikila"
    assert domain.wallet_amount == "1500.00"
    assert domain.activation_paid is True
    assert domain.service_tier_max == 3


@pytest.mark.asyncio
async def test_bank_repo_mapping():
    method_id = uuid4()
    prov_id = uuid4()
    now = datetime.now(timezone.utc)
    entity = ProviderPaymentMethod(
        id=method_id,
        provider_id=prov_id,
        method_type="bank",
        method_code="cbe",
        method_name="Commercial Bank of Ethiopia",
        holder_name="Abebe Bikila",
        account_number="1000123456789",
        is_default=True,
        is_active=True,
        currency="ETB",
        metadata_={},
        created_at=now,
        updated_at=now,
    )

    session = RepoMockSession(scalar_one_or_none_value=entity)
    repo = ProviderBankRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(entity)
    assert domain.id == method_id
    assert domain.provider_id == prov_id
    assert domain.account_number == "1000123456789"
    assert domain.is_default is True


@pytest.mark.asyncio
async def test_company_repo_mapping():
    comp_id = uuid4()
    prov_id = uuid4()
    now = datetime.now(timezone.utc)
    entity = Company(
        id=comp_id,
        provider_id=prov_id,
        name="Abebe Tech Solutions",
        company_name="Abebe Tech",
        industry="Home Maintenance",
        created_at=now,
        updated_at=now,
    )

    session = RepoMockSession(scalar_one_or_none_value=entity)
    repo = ProviderCompanyRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(entity)
    assert domain.id == comp_id
    assert domain.provider_id == prov_id
    assert domain.industry == "Home Maintenance"


@pytest.mark.asyncio
async def test_verify_document_repo_mapping():
    doc_id = uuid4()
    prov_id = uuid4()
    now = datetime.now(timezone.utc)
    entity = VerifyDocument(
        id=doc_id,
        provider_id=prov_id,
        provider_name="Abebe Bikila",
        document_image="https://storage.googleapis.com/docs/trade_license.jpg",
        is_verify=None,
        created_at=now,
    )

    session = RepoMockSession(scalar_one_or_none_value=entity)
    repo = VerifyDocumentRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(entity, document_name="Trade License", sub_category_name="Plumbing")
    assert domain.id == doc_id
    assert domain.provider_id == prov_id
    assert domain.document_name == "Trade License"
    assert domain.sub_category_name == "Plumbing"
    assert domain.is_verify is None

