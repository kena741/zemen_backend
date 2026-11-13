"""Integration tests for Admin Documents and Internal Documents API endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.security.admin_deps import AdminContext
from app.domain.document import AdminInternalDocumentDomain, DocumentTypeDomain
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


def test_list_document_types_endpoint(api_client, super_admin_context):
    doc_id = uuid4()
    mock_doc = DocumentTypeDomain(
        id=doc_id,
        name="Business License",
        active=True,
        description="Official business registration",
    )

    with patch("app.api.v1.routers.admin.documents._get_document_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.list_document_types = AsyncMock(return_value=[mock_doc])

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.get("/api/v1/admin/documents")

        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == str(doc_id)
        assert data[0]["name"] == "Business License"
        assert data[0]["active"] is True


def test_create_document_type_endpoint(api_client, super_admin_context):
    doc_id = uuid4()
    mock_doc = DocumentTypeDomain(
        id=doc_id,
        name="Tax Identification Number (TIN)",
        active=True,
    )

    with patch("app.api.v1.routers.admin.documents._get_document_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.create_document_type = AsyncMock(return_value=mock_doc)

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.post(
            "/api/v1/admin/documents",
            json={"name": "Tax Identification Number (TIN)", "active": True},
        )

        assert res.status_code == 201
        data = res.json()["data"]
        assert data["id"] == str(doc_id)
        assert data["name"] == "Tax Identification Number (TIN)"


def test_update_document_type_endpoint(api_client, super_admin_context):
    doc_id = uuid4()
    mock_doc = DocumentTypeDomain(
        id=doc_id,
        name="Updated Name",
        active=False,
    )

    with patch("app.api.v1.routers.admin.documents._get_document_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.update_document_type = AsyncMock(return_value=mock_doc)

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.patch(
            f"/api/v1/admin/documents/{doc_id}",
            json={"name": "Updated Name", "active": False},
        )

        assert res.status_code == 200
        data = res.json()["data"]
        assert data["name"] == "Updated Name"
        assert data["active"] is False


def test_delete_document_type_endpoint(api_client, super_admin_context):
    doc_id = uuid4()

    with patch("app.api.v1.routers.admin.documents._get_document_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.delete_document_type = AsyncMock(return_value=None)

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.delete(f"/api/v1/admin/documents/{doc_id}")

        assert res.status_code == 200
        assert res.json() == {"ok": True}


def test_list_internal_documents_endpoint(api_client, super_admin_context):
    doc_id = uuid4()
    mock_doc = AdminInternalDocumentDomain(
        id=doc_id,
        title="Safety Guidelines",
        category="policy",
        file_name="safety.pdf",
        storage_path="library/safety.pdf",
        preview_url="https://cdn.example.com/library/safety.pdf",
    )

    with patch("app.api.v1.routers.admin.documents._get_document_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.list_internal_documents = AsyncMock(return_value=[mock_doc])

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.get("/api/v1/admin/internal-documents")

        assert res.status_code == 200
        docs = res.json()["documents"]
        assert len(docs) == 1
        assert docs[0]["id"] == str(doc_id)
        assert docs[0]["title"] == "Safety Guidelines"
        assert docs[0]["fileName"] == "safety.pdf"
        assert docs[0]["previewUrl"] == "https://cdn.example.com/library/safety.pdf"


def test_create_internal_document_endpoint(api_client, super_admin_context):
    doc_id = uuid4()
    mock_doc = AdminInternalDocumentDomain(
        id=doc_id,
        title="Provider Agreement",
        category="agreement",
        file_name="agreement.pdf",
        storage_path="library/agreement.pdf",
    )

    with patch("app.api.v1.routers.admin.documents._get_document_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.create_internal_document = AsyncMock(return_value=mock_doc)

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.post(
            "/api/v1/admin/internal-documents",
            json={
                "title": "Provider Agreement",
                "category": "agreement",
                "fileName": "agreement.pdf",
                "storagePath": "library/agreement.pdf",
            },
        )

        assert res.status_code == 201
        doc = res.json()["document"]
        assert doc["id"] == str(doc_id)
        assert doc["title"] == "Provider Agreement"
        assert doc["fileName"] == "agreement.pdf"


def test_delete_internal_document_endpoint(api_client, super_admin_context):
    doc_id = uuid4()

    with patch("app.api.v1.routers.admin.documents._get_document_service") as mock_get_svc:
        mock_svc = mock_get_svc.return_value
        mock_svc.delete_internal_document = AsyncMock(return_value=None)

        db = ApiTestDbSession()
        client = api_client(admin_context=super_admin_context, db_session=db)
        res = client.delete(f"/api/v1/admin/internal-documents/{doc_id}")

        assert res.status_code == 200
        assert res.json() == {"ok": True}

