"""Service for Admin Verification of provider documents."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.core.notifications.fcm import FCMService, get_fcm_service
from app.core.security.admin_deps import AdminContext
from app.core.services.admin.audit_service import AdminAuditService
from app.domain.verification import VerifyDocumentDomain
from app.persistence.repositories.provider_repo import ProviderRepository
from app.persistence.repositories.verify_document_repo import VerifyDocumentRepository


class VerificationAdminService:
    def __init__(
        self,
        verify_repo: VerifyDocumentRepository,
        provider_repo: ProviderRepository,
        audit_service: AdminAuditService,
        fcm_service: FCMService | None = None,
    ) -> None:
        self.verify_repo = verify_repo
        self.provider_repo = provider_repo
        self.audit_service = audit_service
        self.fcm_service = fcm_service or get_fcm_service()

    async def list_verify_documents(self) -> list[VerifyDocumentDomain]:
        return await self.verify_repo.list_enriched()

    async def count_pending(self) -> int:
        return await self.verify_repo.count_pending()

    async def approve_document(
        self,
        doc_id: UUID,
        ctx: AdminContext | None = None,
    ) -> VerifyDocumentDomain:
        doc = await self.verify_repo.get_enriched_by_id(doc_id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        updated = await self.verify_repo.update_verification_status(doc_id, is_verify=True)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        # Merge subcategory IDs if document has linked subcategories
        if doc.document_id:
            subcat_ids = await self.verify_repo.get_subcategories_for_document(doc.document_id)
            if subcat_ids:
                provider = await self.provider_repo.get_by_id(doc.provider_id)
                if provider:
                    current = set(provider.verified_subcategory_ids)
                    current.update(subcat_ids)
                    await self.provider_repo.update(doc.provider_id, {"verified_subcategory_ids": list(current)})

        await self.audit_service.log_action(
            action="verify",
            resource_type="verify_document",
            resource_id=str(doc_id),
            summary=f"Approved document '{doc.document_name or doc.id}' for provider {doc.provider_name or doc.provider_id}",
            ctx=ctx,
        )
        return updated

    async def reject_document(
        self,
        doc_id: UUID,
        rejection_reason: str,
        provider_name: str | None = None,
        document_name: str | None = None,
        ctx: AdminContext | None = None,
    ) -> VerifyDocumentDomain:
        doc = await self.verify_repo.get_enriched_by_id(doc_id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        updated = await self.verify_repo.update_verification_status(doc_id, is_verify=False)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        # Notify provider via push
        provider = await self.provider_repo.get_by_id(doc.provider_id)
        if provider and provider.fcm_token:
            title = "Document Rejected"
            body = f"Your document '{doc.document_name or 'verification document'}' was rejected: {rejection_reason}"
            await self.fcm_service.send_to_token(
                token=provider.fcm_token,
                title=title,
                body=body,
                data={
                    "route": "/verification",
                    "event": "document_rejected",
                    "document_id": str(doc.document_id) if doc.document_id else "",
                    "reason": rejection_reason,
                },
            )

        await self.audit_service.log_action(
            action="reject",
            resource_type="verify_document",
            resource_id=str(doc_id),
            summary=f"Rejected document '{doc.document_name or doc.id}' for provider {doc.provider_name or doc.provider_id}. Reason: {rejection_reason}",
            metadata={"rejection_reason": rejection_reason},
            ctx=ctx,
        )
        return updated

    async def approve_all_pending(
        self,
        provider_id: UUID,
        ctx: AdminContext | None = None,
    ) -> list[VerifyDocumentDomain]:
        updated_docs = await self.verify_repo.approve_all_pending(provider_id)
        # Collect and merge all subcategory ids
        subcat_ids: set[UUID] = set()
        for d in updated_docs:
            if d.document_id:
                ids = await self.verify_repo.get_subcategories_for_document(d.document_id)
                subcat_ids.update(ids)

        if subcat_ids:
            provider = await self.provider_repo.get_by_id(provider_id)
            if provider:
                current = set(provider.verified_subcategory_ids)
                current.update(subcat_ids)
                await self.provider_repo.update(provider_id, {"verified_subcategory_ids": list(current)})

        await self.audit_service.log_action(
            action="verify_all_pending",
            resource_type="provider",
            resource_id=str(provider_id),
            summary=f"Approved all pending documents ({len(updated_docs)}) for provider {provider_id}",
            ctx=ctx,
        )
        return updated_docs

    async def reapprove_all_rejected(
        self,
        provider_id: UUID,
        ctx: AdminContext | None = None,
    ) -> list[VerifyDocumentDomain]:
        updated_docs = await self.verify_repo.reapprove_all_rejected(provider_id)
        subcat_ids: set[UUID] = set()
        for d in updated_docs:
            if d.document_id:
                ids = await self.verify_repo.get_subcategories_for_document(d.document_id)
                subcat_ids.update(ids)

        if subcat_ids:
            provider = await self.provider_repo.get_by_id(provider_id)
            if provider:
                current = set(provider.verified_subcategory_ids)
                current.update(subcat_ids)
                await self.provider_repo.update(provider_id, {"verified_subcategory_ids": list(current)})

        await self.audit_service.log_action(
            action="reapprove_all_rejected",
            resource_type="provider",
            resource_id=str(provider_id),
            summary=f"Reapproved all rejected documents ({len(updated_docs)}) for provider {provider_id}",
            ctx=ctx,
        )
        return updated_docs

    async def upload_verification_document(
        self,
        provider_id: UUID,
        document_id: UUID,
        document_image: str,
        ctx: AdminContext | None = None,
    ) -> VerifyDocumentDomain:
        provider = await self.provider_repo.get_by_id(provider_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

        domain = await self.verify_repo.replace_document_for_provider(
            provider_id=provider_id,
            document_id=document_id,
            document_image=document_image,
            provider_name=provider.full_name,
            provider_email=provider.email,
        )

        await self.audit_service.log_action(
            action="upload_verification",
            resource_type="verify_document",
            resource_id=str(domain.id),
            summary=f"Admin uploaded verification document for provider {provider.full_name}",
            ctx=ctx,
        )
        return domain

