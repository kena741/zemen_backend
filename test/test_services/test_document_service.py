"""Unit tests for DocumentAdminService."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.security.admin_deps import AdminContext
from app.core.services.admin.audit_service import AdminAuditService
from app.core.services.admin.document_service import DocumentAdminService
from app.domain.document import AdminInternalDocumentDomain, DocumentTypeDomain
from app.persistence.repositories.activity_log_repo import ActivityLogRepository
from app.persistence.repositories.document_repo import DocumentTypeRepository
from app.persistence.repositories.internal_document_repo import AdminInternalDocumentRepository
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
def document_service():
    session = ServiceMockSession()
    doc_repo = DocumentTypeRepository(session)  # type: ignore[arg-type]
    internal_repo = AdminInternalDocumentRepository(session)  # type: ignore[arg-type]
    audit_repo = ActivityLogRepository(session)  # type: ignore[arg-type]
    audit_service = AdminAuditService(audit_repo)

    service = DocumentAdminService(
        document_repo=doc_repo,
        internal_repo=internal_repo,
        audit_service=audit_service,
    )
    return service, doc_repo, internal_repo, audit_service, session


@pytest.mark.asyncio
async def test_create_document_type(document_service, mock_context):
    service, doc_repo, _, _, _ = document_service
    doc_id = uuid4()
    mock_domain = DocumentTypeDomain(
        id=doc_id,
        name="Kebele ID",
        active=True,
        description="Kebele resident identification card",
    )
    doc_repo.create = AsyncMock(return_value=MagicMock())
    doc_repo.to_domain = MagicMock(return_value=mock_domain)

    res = await service.create_document_type(
        name="Kebele ID",
        active=True,
        description="Kebele resident identification card",
        ctx=mock_context,
    )

    assert res.id == doc_id
    assert res.name == "Kebele ID"
    assert res.active is True


@pytest.mark.asyncio
async def test_update_document_type(document_service, mock_context):
    service, doc_repo, _, _, _ = document_service
    doc_id = uuid4()
    mock_domain = DocumentTypeDomain(
        id=doc_id,
        name="National ID",
        active=False,
    )
    doc_repo.get_by_id = AsyncMock(return_value=MagicMock())
    doc_repo.update = AsyncMock(return_value=True)
    doc_repo.to_domain = MagicMock(return_value=mock_domain)

    res = await service.update_document_type(
        doc_id=doc_id,
        updates={"name": "National ID", "active": False},
        ctx=mock_context,
    )

    assert res.id == doc_id
    assert res.name == "National ID"
    assert res.active is False


@pytest.mark.asyncio
async def test_create_internal_document(document_service, mock_context):
    service, _, internal_repo, _, _ = document_service
    doc_id = uuid4()
    mock_internal = AdminInternalDocumentDomain(
        id=doc_id,
        title="Privacy Policy",
        category="policy",
        file_name="privacy.pdf",
        storage_path="library/privacy.pdf",
    )
    internal_repo.create = AsyncMock(return_value=MagicMock())
    internal_repo.to_domain = MagicMock(return_value=mock_internal)

    res = await service.create_internal_document(
        title="Privacy Policy",
        file_name="privacy.pdf",
        storage_path="library/privacy.pdf",
        category="policy",
        ctx=mock_context,
    )

    assert res.id == doc_id
    assert res.title == "Privacy Policy"
    assert res.category == "policy"


@pytest.mark.asyncio
async def test_delete_internal_document(document_service, mock_context):
    service, _, internal_repo, _, _ = document_service
    doc_id = uuid4()
    internal_repo.get_by_id = AsyncMock(return_value=MagicMock())
    internal_repo.to_domain = MagicMock(return_value=MagicMock())
    internal_repo.delete = AsyncMock(return_value=True)

    await service.delete_internal_document(doc_id=doc_id, ctx=mock_context)
    internal_repo.delete.assert_called_once_with(doc_id)
