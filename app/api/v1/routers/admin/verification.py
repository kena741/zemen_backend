"""Admin Verification API router."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.admin.requests.verification import (
    RejectVerificationDocumentRequest,
    UploadVerificationDocumentRequest,
)
from app.api.v1.schemas.admin.responses.verification import (
    NavPendingCountResponse,
    VerifyDocumentItemResponse,
    VerifyDocumentListResponse,
    VerifyDocumentSingleResponse,
)
from app.core.security.admin_deps import AdminContext, require_admin_permission
from app.core.services.admin.audit_service import AdminAuditService
from app.core.services.admin.verification_service import VerificationAdminService
from app.persistence.repositories.activity_log_repo import ActivityLogRepository
from app.persistence.repositories.provider_repo import ProviderRepository
from app.persistence.repositories.verify_document_repo import VerifyDocumentRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/admin", tags=["admin-verification"])

Db = Annotated[AsyncSession, Depends(get_db)]
CanVerifyProviders = Annotated[AdminContext, Depends(require_admin_permission("providers:verify"))]
CanWriteProviders = Annotated[AdminContext, Depends(require_admin_permission("providers:write"))]


class BulkApproveRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    provider_id: UUID = Field(alias="providerId")


def _get_verification_service(db: AsyncSession) -> VerificationAdminService:
    audit_repo = ActivityLogRepository(db)
    audit_service = AdminAuditService(audit_repo)
    verify_repo = VerifyDocumentRepository(db)
    provider_repo = ProviderRepository(db)
    return VerificationAdminService(
        verify_repo=verify_repo,
        provider_repo=provider_repo,
        audit_service=audit_service,
    )


@router.get(
    "/verify-documents",
    response_model=VerifyDocumentListResponse,
    operation_id="admin_verification_list",
    summary="List verification documents",
)
async def list_verify_documents(
    _: CanVerifyProviders,
    db: Db,
) -> VerifyDocumentListResponse:
    service = _get_verification_service(db)
    docs = await service.list_verify_documents()
    return VerifyDocumentListResponse(
        data=[VerifyDocumentItemResponse.model_validate(d) for d in docs]
    )


@router.post(
    "/verify-documents/{doc_id}/approve",
    response_model=VerifyDocumentSingleResponse,
    operation_id="admin_verification_approve",
    summary="Approve verification document",
)
async def approve_document(
    doc_id: UUID,
    ctx: CanVerifyProviders,
    db: Db,
) -> VerifyDocumentSingleResponse:
    service = _get_verification_service(db)
    updated = await service.approve_document(doc_id, ctx=ctx)
    return VerifyDocumentSingleResponse(data=VerifyDocumentItemResponse.model_validate(updated))


@router.post(
    "/verify-documents/{doc_id}/reject",
    response_model=VerifyDocumentSingleResponse,
    operation_id="admin_verification_reject",
    summary="Reject verification document",
)
async def reject_document(
    doc_id: UUID,
    body: RejectVerificationDocumentRequest,
    ctx: CanVerifyProviders,
    db: Db,
) -> VerifyDocumentSingleResponse:
    service = _get_verification_service(db)
    updated = await service.reject_document(
        doc_id=doc_id,
        rejection_reason=body.rejection_reason,
        provider_name=body.provider_name,
        document_name=body.document_name,
        ctx=ctx,
    )
    return VerifyDocumentSingleResponse(data=VerifyDocumentItemResponse.model_validate(updated))


@router.post(
    "/verify-documents/approve-all-pending",
    response_model=VerifyDocumentListResponse,
    operation_id="admin_verification_approve_all_pending",
    summary="Approve all pending documents for a provider",
)
async def approve_all_pending(
    body: BulkApproveRequest,
    ctx: CanVerifyProviders,
    db: Db,
) -> VerifyDocumentListResponse:
    service = _get_verification_service(db)
    docs = await service.approve_all_pending(body.provider_id, ctx=ctx)
    return VerifyDocumentListResponse(
        data=[VerifyDocumentItemResponse.model_validate(d) for d in docs]
    )


@router.post(
    "/verify-documents/reapprove-all-rejected",
    response_model=VerifyDocumentListResponse,
    operation_id="admin_verification_reapprove_all_rejected",
    summary="Re-approve all rejected documents for a provider",
)
async def reapprove_all_rejected(
    body: BulkApproveRequest,
    ctx: CanVerifyProviders,
    db: Db,
) -> VerifyDocumentListResponse:
    service = _get_verification_service(db)
    docs = await service.reapprove_all_rejected(body.provider_id, ctx=ctx)
    return VerifyDocumentListResponse(
        data=[VerifyDocumentItemResponse.model_validate(d) for d in docs]
    )


@router.post(
    "/providers/{provider_id}/verify-documents",
    response_model=VerifyDocumentSingleResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_verification_upload",
    summary="Admin upload verification document for provider",
)
async def upload_verification_document(
    provider_id: UUID,
    body: UploadVerificationDocumentRequest,
    ctx: CanWriteProviders,
    db: Db,
) -> VerifyDocumentSingleResponse:
    service = _get_verification_service(db)
    doc = await service.upload_verification_document(
        provider_id=provider_id,
        document_id=body.document_id,
        document_image=body.document_image,
        ctx=ctx,
    )
    return VerifyDocumentSingleResponse(data=VerifyDocumentItemResponse.model_validate(doc))


@router.get(
    "/nav-action-counts",
    response_model=NavPendingCountResponse,
    operation_id="admin_verification_nav_counts",
    summary="Get pending verification action counts for sidebar",
)
async def get_nav_action_counts(
    ctx: CanVerifyProviders,
    db: Db,
) -> NavPendingCountResponse:
    service = _get_verification_service(db)
    pending_count = await service.count_pending()
    return NavPendingCountResponse(counts={"/admin/verify-documents": pending_count})
