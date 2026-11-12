"""Unit tests for CatalogAdminService."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.security.admin_deps import AdminContext
from app.core.services.admin.audit_service import AdminAuditService
from app.core.services.admin.catalog_service import CatalogAdminService
from app.domain.catalog import CategoryDomain, SubCategoryDomain
from app.persistence.repositories.activity_log_repo import ActivityLogRepository
from app.persistence.repositories.category_repo import CategoryRepository
from app.persistence.repositories.service_repo import ServiceRepository
from app.persistence.repositories.subcategory_repo import SubCategoryRepository
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
def catalog_service():
    session = ServiceMockSession()
    cat_repo = CategoryRepository(session)  # type: ignore[arg-type]
    subcat_repo = SubCategoryRepository(session)  # type: ignore[arg-type]
    srv_repo = ServiceRepository(session)  # type: ignore[arg-type]
    audit_repo = ActivityLogRepository(session)  # type: ignore[arg-type]
    audit_service = AdminAuditService(audit_repo)

    service = CatalogAdminService(
        category_repo=cat_repo,
        subcategory_repo=subcat_repo,
        service_repo=srv_repo,
        audit_service=audit_service,
    )
    return service, cat_repo, subcat_repo, srv_repo, audit_service


@pytest.mark.asyncio
async def test_create_category_success(catalog_service, mock_context):
    service, cat_repo, _, _, _ = catalog_service
    mock_domain = CategoryDomain(
        id=uuid4(),
        category_name="Plumbing",
        image="https://cdn.example.com/plumbing.png",
        active=True,
    )
    cat_repo.create_category = AsyncMock(return_value=mock_domain)

    domain = await service.create_category(
        category_name="Plumbing",
        image="https://cdn.example.com/plumbing.png",
        ctx=mock_context,
    )
    assert domain.category_name == "Plumbing"
    cat_repo.create_category.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_subcategory_success(catalog_service, mock_context):
    service, _, subcat_repo, _, _ = catalog_service
    cat_id = uuid4()
    doc_id = uuid4()
    mock_domain = SubCategoryDomain(
        id=uuid4(),
        sub_category_name="Pipe Repair",
        category_id=cat_id,
        document_ids=[doc_id],
    )
    subcat_repo.create_subcategory = AsyncMock(return_value=mock_domain)

    domain = await service.create_subcategory(
        sub_category_name="Pipe Repair",
        category_id=cat_id,
        document_ids=[doc_id],
        ctx=mock_context,
    )
    assert domain.sub_category_name == "Pipe Repair"
    assert domain.document_ids == [doc_id]
    subcat_repo.create_subcategory.assert_awaited_once()


@pytest.mark.asyncio
async def test_decide_feature_request_success(catalog_service, mock_context):
    service, _, _, srv_repo, _ = catalog_service
    srv_id = uuid4()
    srv_repo.update_feature_request = AsyncMock(return_value=True)

    ok = await service.decide_feature_request(
        service_id=srv_id,
        decision="accept",
        ctx=mock_context,
    )
    assert ok is True
    srv_repo.update_feature_request.assert_awaited_once_with(
        service_id=srv_id,
        feature=True,
        feature_status="accepted",
    )
