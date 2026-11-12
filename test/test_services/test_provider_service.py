"""Unit tests for ProviderAdminService and VerificationAdminService."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.security.admin_deps import AdminContext
from app.core.services.admin.audit_service import AdminAuditService
from app.core.services.admin.provider_service import ProviderAdminService
from app.core.services.admin.verification_service import VerificationAdminService
from app.domain.provider import ProviderDomain
from app.domain.verification import VerifyDocumentDomain
from app.persistence.repositories.activity_log_repo import ActivityLogRepository
from app.persistence.repositories.document_delivery_repo import DocumentDeliveryRepository
from app.persistence.repositories.provider_bank_repo import ProviderBankRepository
from app.persistence.repositories.provider_company_repo import ProviderCompanyRepository
from app.persistence.repositories.provider_repo import ProviderRepository
from app.persistence.repositories.verify_document_repo import VerifyDocumentRepository
from .conftest import ServiceMockSession


@pytest.fixture
def mock_context() -> AdminContext:
    return AdminContext(
        admin_id=uuid4(),
        user_id=uuid4(),
        email="superadmin@lolelink.com",
        full_name="Super Admin",
        role="super_admin",
        permissions=["*"],
    )


@pytest.fixture
def provider_service():
    session = ServiceMockSession()
    prov_repo = ProviderRepository(session)  # type: ignore[arg-type]
    bank_repo = ProviderBankRepository(session)  # type: ignore[arg-type]
    comp_repo = ProviderCompanyRepository(session)  # type: ignore[arg-type]
    deliv_repo = DocumentDeliveryRepository(session)  # type: ignore[arg-type]
    audit_repo = ActivityLogRepository(session)  # type: ignore[arg-type]
    audit_service = AdminAuditService(audit_repo)

    fcm_mock = MagicMock()
    fcm_mock.send_to_token = AsyncMock(return_value={"sent": True, "message_id": "msg-123"})

    service = ProviderAdminService(
        provider_repo=prov_repo,
        bank_repo=bank_repo,
        company_repo=comp_repo,
        delivery_repo=deliv_repo,
        audit_service=audit_service,
        fcm_service=fcm_mock,
    )
    return service, prov_repo, audit_service, session


@pytest.mark.asyncio
async def test_create_provider_success(provider_service, mock_context):
    service, prov_repo, audit_service, session = provider_service
    prov_repo.get_by_email = AsyncMock(return_value=None)
    prov_repo.get_by_slug = AsyncMock(return_value=None)

    now = datetime.now(timezone.utc)
    mock_domain = ProviderDomain(
        id=uuid4(),
        user_id=uuid4(),
        first_name="Sara",
        last_name="Bekele",
        email="sara@example.com",
        phone_number="+251922334455",
        created_at=now,
        updated_at=now,
    )
    prov_repo.create = AsyncMock(return_value=mock_domain)

    domain, temp_pwd, sms = await service.create_provider(
        first_name="Sara",
        last_name="Bekele",
        email="sara@example.com",
        phone="+251922334455",
        ctx=mock_context,
    )

    assert domain.email == "sara@example.com"
    assert domain.full_name == "Sara Bekele"
    assert len(temp_pwd) >= 8
    prov_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_provider_duplicate_email(provider_service, mock_context):
    service, prov_repo, _, _ = provider_service
    prov_repo.get_by_email = AsyncMock(
        return_value=ProviderDomain(id=uuid4(), user_id=uuid4(), email="exists@example.com")
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.create_provider(
            first_name="Duplicate",
            email="exists@example.com",
            ctx=mock_context,
        )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_verify_service_approve_merges_subcategories(mock_context):
    session = ServiceMockSession()
    verify_repo = VerifyDocumentRepository(session)  # type: ignore[arg-type]
    prov_repo = ProviderRepository(session)  # type: ignore[arg-type]
    audit_repo = ActivityLogRepository(session)  # type: ignore[arg-type]
    audit_service = AdminAuditService(audit_repo)

    subcat_id = uuid4()
    prov_id = uuid4()
    doc_id = uuid4()
    now = datetime.now(timezone.utc)

    doc_domain = VerifyDocumentDomain(
        id=doc_id,
        provider_id=prov_id,
        document_id=uuid4(),
        document_name="Driver License",
        created_at=now,
        is_verify=None,
    )
    verify_repo.get_enriched_by_id = AsyncMock(return_value=doc_domain)
    verify_repo.update_verification_status = AsyncMock(return_value=doc_domain)
    verify_repo.get_subcategories_for_document = AsyncMock(return_value=[subcat_id])

    prov_domain = ProviderDomain(
        id=prov_id,
        user_id=uuid4(),
        verified_subcategory_ids=[],
    )
    prov_repo.get_by_id = AsyncMock(return_value=prov_domain)
    prov_repo.update = AsyncMock(return_value=prov_domain)

    v_service = VerificationAdminService(
        verify_repo=verify_repo,
        provider_repo=prov_repo,
        audit_service=audit_service,
    )

    await v_service.approve_document(doc_id, ctx=mock_context)
    prov_repo.update.assert_awaited_once()
    call_args = prov_repo.update.call_args[0]
    assert call_args[0] == prov_id
    assert subcat_id in call_args[1]["verified_subcategory_ids"]
