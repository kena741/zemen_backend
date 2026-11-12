"""Admin Document Types and Internal Documents API router."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.admin.requests.documents import (
    CreateDocumentTypeRequest,
    CreateInternalDocumentRequest,
    UpdateDocumentTypeRequest,
)
from app.api.v1.schemas.admin.responses.documents import (
    AdminInternalDocumentListResponse,
    AdminInternalDocumentResponseItem,
    AdminInternalDocumentSingleResponse,
    DocumentTypeListResponse,
    DocumentTypeResponseItem,
    DocumentTypeSingleResponse,
)
from app.core.security.admin_deps import AdminContext, require_admin_permission
from app.core.services.admin.audit_service import AdminAuditService
from app.core.services.admin.document_service import DocumentAdminService
from app.persistence.repositories.activity_log_repo import ActivityLogRepository
from app.persistence.repositories.document_repo import DocumentTypeRepository
from app.persistence.repositories.internal_document_repo import AdminInternalDocumentRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/admin", tags=["admin-documents"])

Db = Annotated[AsyncSession, Depends(get_db)]
CanReadDocuments = Annotated[AdminContext, Depends(require_admin_permission("documents:read"))]
CanWriteDocuments = Annotated[AdminContext, Depends(require_admin_permission("documents:write"))]


def _get_document_service(db: AsyncSession) -> DocumentAdminService:
    doc_repo = DocumentTypeRepository(db)
    internal_repo = AdminInternalDocumentRepository(db)
    audit_repo = ActivityLogRepository(db)
    audit_service = AdminAuditService(audit_repo)

    return DocumentAdminService(
        document_repo=doc_repo,
        internal_repo=internal_repo,
        audit_service=audit_service,
    )


# --- Document Types (`documents` table) ---------------------------------------


@router.get(
    "/documents",
    response_model=DocumentTypeListResponse,
    operation_id="admin_documents_list_types",
    summary="List all document types ordered by name",
)
async def list_document_types(_: CanReadDocuments, db: Db) -> DocumentTypeListResponse:
    service = _get_document_service(db)
    items = await service.list_document_types()
    return DocumentTypeListResponse(data=[DocumentTypeResponseItem.model_validate(i) for i in items])


@router.post(
    "/documents",
    response_model=DocumentTypeSingleResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_documents_create_type",
    summary="Create a new document type",
)
async def create_document_type(
    body: CreateDocumentTypeRequest,
    ctx: CanWriteDocuments,
    db: Db,
) -> DocumentTypeSingleResponse:
    service = _get_document_service(db)
    created = await service.create_document_type(
        name=body.name,
        active=body.active,
        description=body.description,
        ctx=ctx,
    )
    return DocumentTypeSingleResponse(data=DocumentTypeResponseItem.model_validate(created))


@router.patch(
    "/documents/{document_id}",
    response_model=DocumentTypeSingleResponse,
    operation_id="admin_documents_update_type_path",
    summary="Update document type by path id",
)
async def update_document_type_path(
    document_id: UUID,
    body: UpdateDocumentTypeRequest,
    ctx: CanWriteDocuments,
    db: Db,
) -> DocumentTypeSingleResponse:
    service = _get_document_service(db)
    updated = await service.update_document_type(
        doc_id=document_id,
        updates=body.model_dump(exclude_unset=True, exclude={"id"}),
        ctx=ctx,
    )
    return DocumentTypeSingleResponse(data=DocumentTypeResponseItem.model_validate(updated))


@router.patch(
    "/documents",
    response_model=DocumentTypeSingleResponse,
    operation_id="admin_documents_update_type_body",
    summary="Update document type by body id",
)
async def update_document_type_body(
    body: UpdateDocumentTypeRequest,
    ctx: CanWriteDocuments,
    db: Db,
) -> DocumentTypeSingleResponse:
    if not body.id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="id is required in body")
    service = _get_document_service(db)
    updated = await service.update_document_type(
        doc_id=body.id,
        updates=body.model_dump(exclude_unset=True, exclude={"id"}),
        ctx=ctx,
    )
    return DocumentTypeSingleResponse(data=DocumentTypeResponseItem.model_validate(updated))


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_200_OK,
    operation_id="admin_documents_delete_type_path",
    summary="Delete document type by path id",
)
async def delete_document_type_path(
    document_id: UUID,
    ctx: CanWriteDocuments,
    db: Db,
) -> dict[str, bool]:
    service = _get_document_service(db)
    await service.delete_document_type(doc_id=document_id, ctx=ctx)
    return {"ok": True}


# --- Admin Internal Documents (`admin_documents` table) -----------------------


@router.get(
    "/internal-documents",
    response_model=AdminInternalDocumentListResponse,
    operation_id="admin_internal_documents_list",
    summary="List internal documents library with preview URLs",
)
async def list_internal_documents(_: CanReadDocuments, db: Db) -> AdminInternalDocumentListResponse:
    service = _get_document_service(db)
    items = await service.list_internal_documents()
    return AdminInternalDocumentListResponse(
        documents=[AdminInternalDocumentResponseItem.model_validate(i) for i in items]
    )


@router.post(
    "/internal-documents",
    response_model=AdminInternalDocumentSingleResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_internal_documents_create",
    summary="Create or register uploaded internal document record",
)
async def create_internal_document(
    body: CreateInternalDocumentRequest,
    ctx: CanWriteDocuments,
    db: Db,
) -> AdminInternalDocumentSingleResponse:
    service = _get_document_service(db)
    created = await service.create_internal_document(
        title=body.title,
        file_name=body.file_name,
        storage_path=body.storage_path,
        category=body.category,
        mime_type=body.mime_type,
        ctx=ctx,
    )
    return AdminInternalDocumentSingleResponse(
        document=AdminInternalDocumentResponseItem.model_validate(created)
    )


@router.get(
    "/internal-documents/{document_id}",
    response_model=AdminInternalDocumentSingleResponse,
    operation_id="admin_internal_documents_get",
    summary="Get internal document details by ID",
)
async def get_internal_document(
    document_id: UUID,
    _: CanReadDocuments,
    db: Db,
) -> AdminInternalDocumentSingleResponse:
    service = _get_document_service(db)
    doc = await service.get_internal_document(doc_id=document_id)
    return AdminInternalDocumentSingleResponse(
        document=AdminInternalDocumentResponseItem.model_validate(doc)
    )


@router.delete(
    "/internal-documents/{document_id}",
    status_code=status.HTTP_200_OK,
    operation_id="admin_internal_documents_delete",
    summary="Delete internal document by ID",
)
async def delete_internal_document(
    document_id: UUID,
    ctx: CanWriteDocuments,
    db: Db,
) -> dict[str, bool]:
    service = _get_document_service(db)
    await service.delete_internal_document(doc_id=document_id, ctx=ctx)
    return {"ok": True}
