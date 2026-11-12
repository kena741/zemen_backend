"""lolelink-admin endpoints (Plan 6). Permission strings match lolelink-admin."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.admin import (
    AdminMeOut,
    AdminServiceOut,
    ApproveProviderServicesOut,
    FeatureDecisionBody,
    RejectDocumentBody,
    VerifyDocumentOut,
)
from app.api.v1.schemas.common import Page, PageMeta
from app.core.security.admin_deps import AdminContext, RequireAdmin, require_admin_permission
from app.core.services import admin_document_review, admin_service_review
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/admin", tags=["Admin"])

Db = Annotated[AsyncSession, Depends(get_db)]
CanWriteServices = Annotated[AdminContext, Depends(require_admin_permission("services:write"))]
CanReadProviders = Annotated[AdminContext, Depends(require_admin_permission("providers:read"))]
CanVerifyProviders = Annotated[AdminContext, Depends(require_admin_permission("providers:verify"))]


@router.get("/me", response_model=AdminMeOut, operation_id="admin_me", summary="Current admin and resolved permissions")
async def admin_me(ctx: RequireAdmin) -> AdminMeOut:
    return AdminMeOut(
        admin_id=ctx.admin_id,
        user_id=ctx.user_id,
        email=ctx.email,
        full_name=ctx.full_name,
        role=ctx.role,
        permissions=ctx.permissions,
    )


# --- Services: approval + featured listing -------------------------------------------------


@router.post(
    "/services/{service_id}/approve",
    response_model=AdminServiceOut,
    operation_id="admin_approve_service",
    summary="Approve a single service",
)
async def admin_approve_service(service_id: UUID, ctx: CanWriteServices, db: Db) -> AdminServiceOut:
    service = await admin_service_review.get_service(db, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    row = await admin_service_review.approve_service(db, ctx, service)
    return AdminServiceOut.model_validate(row)


@router.post(
    "/providers/{provider_id}/services/approve",
    response_model=ApproveProviderServicesOut,
    operation_id="admin_approve_provider_services",
    summary="Approve every non-archived, unapproved service of a provider",
)
async def admin_approve_provider_services(
    provider_id: UUID, ctx: CanWriteServices, db: Db
) -> ApproveProviderServicesOut:
    ids = await admin_service_review.approve_provider_services(db, ctx, provider_id)
    return ApproveProviderServicesOut(updated_count=len(ids), service_ids=ids)


@router.post(
    "/services/{service_id}/feature",
    response_model=AdminServiceOut,
    operation_id="admin_decide_service_feature",
    summary="Accept / reject a featured request, or remove featured status",
)
async def admin_decide_service_feature(
    service_id: UUID, body: FeatureDecisionBody, ctx: CanWriteServices, db: Db
) -> AdminServiceOut:
    service = await admin_service_review.get_service(db, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    row = await admin_service_review.decide_feature(db, ctx, service, body.decision)
    return AdminServiceOut.model_validate(row)


# --- Provider document verification --------------------------------------------------------


def _doc_out(row, document_name=None, sub_category_name=None) -> VerifyDocumentOut:
    out = VerifyDocumentOut.model_validate(row)
    return out.model_copy(update={"document_name": document_name, "sub_category_name": sub_category_name})


@router.get(
    "/verify-documents",
    response_model=Page[VerifyDocumentOut],
    operation_id="admin_list_verify_documents",
    summary="List provider verification documents",
)
async def admin_list_verify_documents(
    _ctx: CanReadProviders,
    db: Db,
    provider_id: UUID | None = Query(None, alias="providerId"),
    doc_status: Literal["pending", "verified", "rejected"] | None = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Page[VerifyDocumentOut]:
    items = await admin_document_review.list_documents(
        db, provider_id=provider_id, status=doc_status, limit=limit, offset=offset
    )
    return Page(
        items=[_doc_out(i["row"], i["document_name"], i["sub_category_name"]) for i in items],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.post(
    "/verify-documents/{document_row_id}/verify",
    response_model=VerifyDocumentOut,
    operation_id="admin_verify_document",
    summary="Approve one provider document",
)
async def admin_verify_document(document_row_id: UUID, ctx: CanVerifyProviders, db: Db) -> VerifyDocumentOut:
    row = await admin_document_review.get_document(db, document_row_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    try:
        row = await admin_document_review.verify_document(db, ctx, row)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _doc_out(row)


@router.post(
    "/verify-documents/{document_row_id}/reject",
    response_model=VerifyDocumentOut,
    operation_id="admin_reject_document",
    summary="Reject (or revoke approval of) one provider document",
    description="Push notification to the provider is still sent by lolelink-admin via /api/admin/push/notify.",
)
async def admin_reject_document(
    document_row_id: UUID, body: RejectDocumentBody, ctx: CanVerifyProviders, db: Db
) -> VerifyDocumentOut:
    reason = body.reason.strip()
    if not reason:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Rejection reason is required")
    row = await admin_document_review.get_document(db, document_row_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    try:
        row = await admin_document_review.reject_document(db, ctx, row, reason)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _doc_out(row)


@router.post(
    "/providers/{provider_id}/verify-documents/approve-pending",
    response_model=list[VerifyDocumentOut],
    operation_id="admin_approve_pending_documents",
    summary="Approve every pending document of a provider",
)
async def admin_approve_pending_documents(
    provider_id: UUID, ctx: CanVerifyProviders, db: Db
) -> list[VerifyDocumentOut]:
    try:
        rows = await admin_document_review.bulk_verify(db, ctx, provider_id, from_status="pending")
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [_doc_out(r) for r in rows]


@router.post(
    "/providers/{provider_id}/verify-documents/reapprove-rejected",
    response_model=list[VerifyDocumentOut],
    operation_id="admin_reapprove_rejected_documents",
    summary="Re-approve every rejected document of a provider",
)
async def admin_reapprove_rejected_documents(
    provider_id: UUID, ctx: CanVerifyProviders, db: Db
) -> list[VerifyDocumentOut]:
    try:
        rows = await admin_document_review.bulk_verify(db, ctx, provider_id, from_status="rejected")
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [_doc_out(r) for r in rows]
