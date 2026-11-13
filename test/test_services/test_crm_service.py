"""Unit tests for JobRequestAdminService."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.security.admin_deps import AdminContext
from app.core.services.admin.audit_service import AdminAuditService
from app.core.services.admin.crm_service import JobRequestAdminService
from app.domain.crm import JobRequestDomain
from app.persistence.repositories.activity_log_repo import ActivityLogRepository
from app.persistence.repositories.job_request_repo import JobRequestRepository
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
def crm_service():
    session = ServiceMockSession()
    job_repo = JobRequestRepository(session)  # type: ignore[arg-type]
    audit_repo = ActivityLogRepository(session)  # type: ignore[arg-type]
    audit_service = AdminAuditService(audit_repo)

    service = JobRequestAdminService(
        job_repo=job_repo,
        audit_service=audit_service,
    )
    return service, job_repo, audit_service, session


@pytest.mark.asyncio
async def test_update_job_request_accept(crm_service, mock_context):
    service, job_repo, _, _ = crm_service
    mock_domain = JobRequestDomain(
        id="jr-100",
        title="House Painting",
        status="accepted",
        accepted=True,
    )
    job_repo.update_job_request = AsyncMock(return_value=MagicMock())
    job_repo.to_domain = MagicMock(return_value=mock_domain)

    res = await service.update_job_request(
        job_id="jr-100",
        action="accept",
        ctx=mock_context,
    )

    assert res.id == "jr-100"
    assert res.status == "accepted"
    assert res.accepted is True


@pytest.mark.asyncio
async def test_delete_single_job_request(crm_service, mock_context):
    service, job_repo, _, _ = crm_service
    job_repo.delete_by_id = AsyncMock(return_value=1)

    count = await service.delete_job_requests(job_id="jr-100", ctx=mock_context)
    assert count == 1
    job_repo.delete_by_id.assert_called_once_with("jr-100")


@pytest.mark.asyncio
async def test_delete_customer_job_requests_bulk(crm_service, mock_context):
    service, job_repo, _, _ = crm_service
    cust_id = uuid4()
    job_repo.delete_all_for_customer = AsyncMock(return_value=3)

    count = await service.delete_job_requests(customer_id=cust_id, ctx=mock_context)
    assert count == 3
    job_repo.delete_all_for_customer.assert_called_once_with(cust_id)

