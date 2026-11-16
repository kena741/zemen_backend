"""Verification document catalog endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.base import MobileApiSchema
from app.core.services.provider_documents import ProviderDocumentService
from app.persistence.repositories.document_repo import DocumentTypeRepository
from app.persistence.repositories.verify_document_repo import VerifyDocumentRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/documents", tags=["Documents"])


class DocumentCatalogOut(MobileApiSchema):
    id: UUID
    name: str
    active: bool = True
    description: str | None = None


def get_provider_document_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderDocumentService:
    return ProviderDocumentService(
        verify_repo=VerifyDocumentRepository(db),
        doc_type_repo=DocumentTypeRepository(db),
    )


@router.get(
    "/catalog",
    response_model=list[DocumentCatalogOut],
    summary="List available verification document types for providers",
)
async def list_document_catalog(
    service: Annotated[ProviderDocumentService, Depends(get_provider_document_service)],
) -> list[DocumentCatalogOut]:
    items = await service.list_catalog_documents()
    return [DocumentCatalogOut.model_validate(item) for item in items]

