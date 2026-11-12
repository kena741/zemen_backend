"""Core service for Document types and Internal documents."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.core.security.admin_deps import AdminContext
from app.core.services.admin.audit_service import AdminAuditService
from app.domain.document import AdminInternalDocumentDomain, DocumentTypeDomain
from app.persistence.repositories.document_repo import DocumentTypeRepository
from app.persistence.repositories.internal_document_repo import AdminInternalDocumentRepository


class DocumentAdminService:
    def __init__(
        self,
        document_repo: DocumentTypeRepository,
        internal_repo: AdminInternalDocumentRepository,
        audit_service: AdminAuditService,
    ) -> None:
        self.document_repo = document_repo
        self.internal_repo = internal_repo
        self.audit_service = audit_service

    # --- Document Types ------------------------------------------------------

    async def list_document_types(self) -> list[DocumentTypeDomain]:
        return await self.document_repo.list_all_documents()

    async def get_document_type(self, doc_id: UUID) -> DocumentTypeDomain:
        d = await self.document_repo.get_by_id(doc_id)
        if not d:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document type not found")
        return self.document_repo.to_domain(d)

    async def create_document_type(
        self,
        name: str,
        active: bool = True,
        description: str | None = None,
        ctx: AdminContext | None = None,
    ) -> DocumentTypeDomain:
        created = await self.document_repo.create({
            "name": name,
            "active": active,
            "description": description,
        })
        domain = self.document_repo.to_domain(created)
        await self.audit_service.log_action(
            action="document_type.create",
            resource_type="document",
            resource_id=str(domain.id),
            summary=f"Created document type '{name}'",
            ctx=ctx,
        )
        return domain

    async def update_document_type(
        self,
        doc_id: UUID,
        updates: dict[str, Any],
        ctx: AdminContext | None = None,
    ) -> DocumentTypeDomain:
        await self.get_document_type(doc_id)
        clean = {k: v for k, v in updates.items() if v is not None}
        updated = await self.document_repo.update(doc_id, clean)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document type not found")

        await self.audit_service.log_action(
            action="document_type.update",
            resource_type="document",
            resource_id=str(doc_id),
            summary=f"Updated document type {doc_id}",
            metadata=clean,
            ctx=ctx,
        )
        entity = await self.document_repo.get_by_id(doc_id)
        return self.document_repo.to_domain(entity)

    async def delete_document_type(self, doc_id: UUID, ctx: AdminContext | None = None) -> None:
        await self.get_document_type(doc_id)
        await self.document_repo.delete(doc_id)
        await self.audit_service.log_action(
            action="document_type.delete",
            resource_type="document",
            resource_id=str(doc_id),
            summary=f"Deleted document type {doc_id}",
            ctx=ctx,
        )

    # --- Internal Documents --------------------------------------------------

    async def list_internal_documents(self) -> list[AdminInternalDocumentDomain]:
        docs = await self.internal_repo.list_all_internal()
        # Enrich with ephemeral signed preview url or CDN link
        for d in docs:
            d.preview_url = f"https://cdn.example.com/{d.storage_path}"
        return docs

    async def get_internal_document(self, doc_id: UUID) -> AdminInternalDocumentDomain:
        entity = await self.internal_repo.get_by_id(doc_id)
        if not entity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internal document not found")
        preview = f"https://cdn.example.com/{entity.storage_path}"
        return self.internal_repo.to_domain(entity, preview_url=preview)

    async def create_internal_document(
        self,
        title: str,
        file_name: str,
        storage_path: str,
        category: str = "other",
        mime_type: str = "application/pdf",
        uploaded_by: UUID | None = None,
        ctx: AdminContext | None = None,
    ) -> AdminInternalDocumentDomain:
        now = datetime.now(timezone.utc)
        created = await self.internal_repo.create({
            "title": title,
            "category": category,
            "file_name": file_name,
            "storage_path": storage_path,
            "mime_type": mime_type,
            "uploaded_by": uploaded_by or (ctx.admin_id if ctx else None),
            "created_at": now,
            "updated_at": now,
        })
        preview = f"https://cdn.example.com/{storage_path}"
        domain = self.internal_repo.to_domain(created, preview_url=preview)

        await self.audit_service.log_action(
            action="internal_document.upload",
            resource_type="admin_document",
            resource_id=str(domain.id),
            summary=f"Uploaded internal document '{title}' ({file_name})",
            metadata={"category": category, "storage_path": storage_path},
            ctx=ctx,
        )
        return domain

    async def delete_internal_document(self, doc_id: UUID, ctx: AdminContext | None = None) -> None:
        await self.get_internal_document(doc_id)
        await self.internal_repo.delete(doc_id)
        await self.audit_service.log_action(
            action="internal_document.delete",
            resource_type="admin_document",
            resource_id=str(doc_id),
            summary=f"Deleted internal document {doc_id}",
            ctx=ctx,
        )
