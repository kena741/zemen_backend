"""Unit tests for CustomerAdminService."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.security.admin_deps import AdminContext
from app.core.services.admin.audit_service import AdminAuditService
from app.core.services.admin.customer_service import CustomerAdminService
from app.domain.customer import CustomerDomain, CustomerStatsDomain
from app.domain.provider import ProviderDomain
from app.persistence.repositories.activity_log_repo import ActivityLogRepository
from app.persistence.repositories.customer_repo import CustomerRepository
from app.persistence.repositories.provider_repo import ProviderRepository
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
def customer_service():
    session = ServiceMockSession()
    cust_repo = CustomerRepository(session)  # type: ignore[arg-type]
    prov_repo = ProviderRepository(session)  # type: ignore[arg-type]
    audit_repo = ActivityLogRepository(session)  # type: ignore[arg-type]
    audit_service = AdminAuditService(audit_repo)

    fcm_mock = MagicMock()
    fcm_mock.send_to_token = AsyncMock(return_value={"sent": True, "message_id": "msg-456"})

    service = CustomerAdminService(
        customer_repo=cust_repo,
        provider_repo=prov_repo,
        audit_service=audit_service,
        fcm_service=fcm_mock,
    )
    return service, cust_repo, prov_repo, audit_service, session


@pytest.mark.asyncio
async def test_create_customer_success(customer_service, mock_context):
    service, cust_repo, _, _, session = customer_service
    cust_repo.get_by_email = AsyncMock(return_value=None)
    cust_repo.get_by_phone = AsyncMock(return_value=None)
    cust_repo.get_by_slug = AsyncMock(return_value=None)

    now = datetime.now(timezone.utc)
    mock_domain = CustomerDomain(
        id=uuid4(),
        user_id=uuid4(),
        first_name="Kenenisa",
        last_name="Bekele",
        phone="+251911887766",
        email="kenenisa@example.com",
        created_at=now,
        updated_at=now,
    )
    cust_repo.create = AsyncMock(return_value=mock_domain)

    domain, temp_pwd, sms = await service.create_customer(
        first_name="Kenenisa",
        last_name="Bekele",
        phone="+251911887766",
        email="kenenisa@example.com",
        ctx=mock_context,
    )

    assert domain.full_name == "Kenenisa Bekele"
    assert len(temp_pwd) >= 8
    cust_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_convert_to_provider_success(customer_service, mock_context):
    service, cust_repo, prov_repo, audit_service, session = customer_service

    cust_id = uuid4()
    user_id = uuid4()
    now = datetime.now(timezone.utc)
    cust_domain = CustomerDomain(
        id=cust_id,
        user_id=user_id,
        first_name="Marta",
        last_name="Tadesse",
        phone="+251933445566",
        email="marta@example.com",
        created_at=now,
    )
    stats_domain = CustomerStatsDomain()

    cust_repo.get_by_id = AsyncMock(return_value=cust_domain)
    cust_repo.get_stats = AsyncMock(return_value=stats_domain)
    prov_repo.get_by_email = AsyncMock(return_value=None)
    prov_repo.get_by_slug = AsyncMock(return_value=None)

    created_prov = ProviderDomain(
        id=uuid4(),
        user_id=user_id,
        first_name="Marta",
        last_name="Tadesse",
        email="marta@example.com",
    )
    prov_repo.create = AsyncMock(return_value=created_prov)

    prov = await service.convert_to_provider(cust_id, ctx=mock_context)
    assert prov.full_name == "Marta Tadesse"
    prov_repo.create.assert_awaited_once()
