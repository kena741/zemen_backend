"""Integration tests for Admin CRM and Job Requests API endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.security.admin_deps import AdminContext
from app.domain.crm import JobRequestDomain
from .conftest import ApiTestDbSession


@pytest.fixture
def super_admin_context() -> AdminContext:
    return AdminContext(
        admin_id=uuid4(),
        user_id=uuid4(),
        email="superadmin@lolelink.com",
        full_name="Super Admin",
        role="super_admin",
        permissions=["*"],
    )


def test_list_job_requests_endpoint(api_client, super_admin_context):
    mock_jr = JobRequestDomain(
        id="jr-888",
        created_at=datetime.now(timezone.utc),
        title="Roof Waterproofing",
        price="3200.00",
        status="pending",
        customer_display_name="Hailu Mergia",
        customer_display_phone="+251911445566",
    )

    with patch("app.api.v1.routers.admin.crm._get_crm_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.list_job_requests = AsyncMock(return_value=[mock_jr])

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.get("/api/v1/admin/job-requests")

        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == "jr-888"
        assert data[0]["title"] == "Roof Waterproofing"
        assert data[0]["customerDisplayName"] == "Hailu Mergia"
        assert data[0]["customerDisplayPhone"] == "+251911445566"


def test_get_job_requests_badge_count(api_client, super_admin_context):
    with patch("app.api.v1.routers.admin.crm._get_crm_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.count_pending_badge = AsyncMock(return_value=5)

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.get("/api/v1/admin/job-requests/badge-count")

        assert res.status_code == 200
        assert res.json() == {"count": 5}


def test_update_job_request_endpoint(api_client, super_admin_context):
    with patch("app.api.v1.routers.admin.crm._get_crm_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.update_job_request = AsyncMock(return_value=MagicMock())

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.patch(
            "/api/v1/admin/job-requests",
            json={"id": "jr-888", "action": "accept"},
        )

        assert res.status_code == 200
        assert res.json() == {"ok": True}


def test_delete_job_request_endpoint(api_client, super_admin_context):
    with patch("app.api.v1.routers.admin.crm._get_crm_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.delete_job_requests = AsyncMock(return_value=1)

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.request(
            "DELETE",
            "/api/v1/admin/job-requests",
            json={"id": "jr-888"},
        )

        assert res.status_code == 200
        assert res.json() == {"ok": True, "deleted": 1}
