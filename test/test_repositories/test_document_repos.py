"""Unit and mapping tests for Document repositories."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.persistence.repositories.document_repo import DocumentTypeRepository
from app.persistence.repositories.internal_document_repo import AdminInternalDocumentRepository
from app.persistence.sqlalchemy.models.admin import AdminDocument, Document
from .conftest import RepoMockSession


@pytest.mark.asyncio
async def test_document_type_repo_to_domain():
    doc_id = uuid4()
    entity = Document(
        id=doc_id,
        name="Business License",
        active=True,
        description="Official government trade license",
    )

    session = RepoMockSession(scalar_one_or_none_value=entity)
    repo = DocumentTypeRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(entity)
    assert domain.id == doc_id
    assert domain.name == "Business License"
    assert domain.active is True
    assert domain.description == "Official government trade license"


@pytest.mark.asyncio
async def test_internal_document_repo_to_domain():
    doc_id = uuid4()
    user_id = uuid4()
    now = datetime.now(timezone.utc)
    entity = AdminDocument(
        id=doc_id,
        title="Terms of Service 2026",
        category="policy",
        file_name="tos_2026.pdf",
        storage_path="library/tos_2026.pdf",
        mime_type="application/pdf",
        uploaded_by=user_id,
        created_at=now,
        updated_at=now,
    )

    session = RepoMockSession(scalar_one_or_none_value=entity)
    repo = AdminInternalDocumentRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(entity, preview_url="https://cdn.example.com/tos.pdf")
    assert domain.id == doc_id
    assert domain.title == "Terms of Service 2026"
    assert domain.category == "policy"
    assert domain.file_name == "tos_2026.pdf"
    assert domain.storage_path == "library/tos_2026.pdf"
    assert domain.preview_url == "https://cdn.example.com/tos.pdf"

