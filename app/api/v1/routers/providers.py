"""Provider profile, company metadata, handymen personnel, and document endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.catalog import ServiceCreate, ServiceOut, ServicePatch
from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.device import FcmTokenBody
from app.api.v1.schemas.handyman import HandymanCreate, HandymanOut, HandymanPatch
from app.api.v1.schemas.provider import (
    CompanyOut,
    CompanyWrite,
    PaymentMethodOut,
    PaymentMethodWrite,
    ProviderCreate,
    ProviderDocumentOut,
    ProviderDocumentsBody,
    ProviderOut,
    ProviderPatch,
)
from app.core.security.deps import RequireAuth, RequireProvider
from app.core.services import (
    booking_service,
    provider_payment_methods,
    provider_service_mgmt,
)
from app.core.services.provider_payment_methods import PaymentMethodConflict
from app.core.services.handyman_service import HandymanService
from app.core.services.provider_documents import ProviderDocumentService
from app.core.services.provider_profile_service import ProviderProfileService
from app.core.services.provider_service_mgmt import ProviderServiceManagementService
from app.domain.exceptions import EntityNotFoundError
from app.domain.provider import CompanyDomain, ProviderDomain
from app.persistence.repositories.document_repo import DocumentTypeRepository
from app.persistence.repositories.handyman_repo import HandymanRepository
from app.persistence.repositories.provider_company_repo import ProviderCompanyRepository
from app.persistence.repositories.provider_repo import ProviderRepository
from app.persistence.repositories.service_repo import ServiceRepository
from app.persistence.repositories.verify_document_repo import VerifyDocumentRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/providers", tags=["Providers"])


def get_provider_profile_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderProfileService:
    return ProviderProfileService(
        provider_repo=ProviderRepository(db),
        company_repo=ProviderCompanyRepository(db),
    )


def get_handyman_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HandymanService:
    return HandymanService(HandymanRepository(db))


def get_provider_document_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderDocumentService:
    return ProviderDocumentService(
        verify_repo=VerifyDocumentRepository(db),
        doc_type_repo=DocumentTypeRepository(db),
    )


def get_provider_service_management(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderServiceManagementService:
    return ProviderServiceManagementService(
        service_repo=ServiceRepository(db),
        provider_repo=ProviderRepository(db),
    )


# ======================== Provider Profile Endpoints ========================


@router.get(
    "/me",
    response_model=ProviderOut,
    summary="Get authenticated provider profile",
)
async def get_my_provider_profile(
    ctx: RequireProvider,
    service: Annotated[ProviderProfileService, Depends(get_provider_profile_service)],
) -> ProviderOut:
    assert ctx.provider_id is not None
    provider = await service.get_profile(ctx.provider_id)
    return ProviderOut.model_validate(provider)


@router.patch(
    "/me",
    response_model=ProviderOut,
    summary="Update authenticated provider profile",
)
async def update_my_provider_profile(
    body: ProviderPatch,
    ctx: RequireProvider,
    service: Annotated[ProviderProfileService, Depends(get_provider_profile_service)],
) -> ProviderOut:
    assert ctx.provider_id is not None
    updated = await service.update_profile(
        provider_id=ctx.provider_id,
        patch=body.model_dump(exclude_unset=True),
    )
    return ProviderOut.model_validate(updated)


@router.put(
    "/me/fcm-token",
    response_model=ProviderOut,
    summary="Update provider FCM push token",
)
async def update_provider_fcm_token(
    body: FcmTokenBody,
    ctx: RequireProvider,
    service: Annotated[ProviderProfileService, Depends(get_provider_profile_service)],
) -> ProviderOut:
    assert ctx.provider_id is not None
    await service.update_fcm_token(ctx.provider_id, body.fcm_token)
    provider = await service.get_profile(ctx.provider_id)
    return ProviderOut.model_validate(provider)


@router.delete(
    "/me",
    response_model=ProviderOut,
    summary="Archive authenticated provider profile",
)
async def archive_my_provider_profile(
    ctx: RequireProvider,
    service: Annotated[ProviderProfileService, Depends(get_provider_profile_service)],
) -> ProviderOut:
    assert ctx.provider_id is not None
    archived = await service.archive_profile(ctx.provider_id)
    return ProviderOut.model_validate(archived)


@router.get(
    "/resolve-id",
    summary="Resolve current provider ID from auth context",
)
async def resolve_provider_id(
    ctx: RequireAuth,
    service: Annotated[ProviderProfileService, Depends(get_provider_profile_service)],
) -> dict[str, str]:
    if ctx.provider_id:
        return {"providerId": str(ctx.provider_id)}
    provider = await service.get_profile_by_user_id(ctx.user_id)
    if not provider:
        raise EntityNotFoundError("Provider linked to user", ctx.user_id)
    return {"providerId": str(provider.id)}


@router.get(
    "/by-phone",
    response_model=ProviderOut,
    summary="Lookup provider profile by phone number",
)
async def get_provider_by_phone(
    service: Annotated[ProviderProfileService, Depends(get_provider_profile_service)],
    phone: str = Query(..., min_length=4),
) -> ProviderOut:
    provider = await service.get_profile_by_phone(phone)
    if not provider:
        raise EntityNotFoundError("Provider", phone)
    return ProviderOut.model_validate(provider)


@router.get(
    "/{provider_id}",
    response_model=ProviderOut,
    summary="Get public provider profile by ID",
)
async def get_provider_by_id(
    provider_id: UUID,
    service: Annotated[ProviderProfileService, Depends(get_provider_profile_service)],
) -> ProviderOut:
    provider = await service.get_profile(provider_id)
    return ProviderOut.model_validate(provider)


# ======================== Provider Company Endpoints ========================


@router.get(
    "/me/company",
    response_model=CompanyOut | None,
    summary="Get provider company details",
)
async def get_provider_company(
    ctx: RequireProvider,
    service: Annotated[ProviderProfileService, Depends(get_provider_profile_service)],
) -> CompanyOut | None:
    assert ctx.provider_id is not None
    company = await service.get_company(ctx.provider_id)
    return CompanyOut.model_validate(company) if company else None


@router.put(
    "/me/company",
    response_model=CompanyOut,
    summary="Upsert provider company details",
)
@router.post(
    "/me/company",
    response_model=CompanyOut,
    summary="Upsert provider company details",
)
async def upsert_provider_company(
    body: CompanyWrite,
    ctx: RequireProvider,
    service: Annotated[ProviderProfileService, Depends(get_provider_profile_service)],
) -> CompanyOut:
    assert ctx.provider_id is not None
    company = await service.upsert_company(
        provider_id=ctx.provider_id,
        values=body.model_dump(exclude_unset=True),
    )
    return CompanyOut.model_validate(company)


# ======================== Handyman Personnel Endpoints ========================


@router.get(
    "/me/handymen",
    response_model=list[HandymanOut],
    summary="List handymen belonging to the authenticated provider",
)
async def list_my_handymen(
    ctx: RequireProvider,
    service: Annotated[HandymanService, Depends(get_handyman_service)],
) -> list[HandymanOut]:
    assert ctx.provider_id is not None
    rows = await service.list_for_provider(ctx.provider_id)
    return [HandymanOut.model_validate(r) for r in rows]


@router.post(
    "/me/handymen",
    response_model=HandymanOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create handyman personnel for the authenticated provider",
)
async def create_handyman_profile(
    body: HandymanCreate,
    ctx: RequireProvider,
    service: Annotated[HandymanService, Depends(get_handyman_service)],
) -> HandymanOut:
    assert ctx.provider_id is not None
    created = await service.create_handyman(
        provider_id=ctx.provider_id,
        data=body.model_dump(exclude_unset=True),
    )
    return HandymanOut.model_validate(created)


@router.get(
    "/me/handymen/{handyman_id}",
    response_model=HandymanOut,
    summary="Get single handyman personnel owned by provider",
)
async def get_my_handyman(
    handyman_id: UUID,
    ctx: RequireProvider,
    service: Annotated[HandymanService, Depends(get_handyman_service)],
) -> HandymanOut:
    assert ctx.provider_id is not None
    item = await service.get_handyman(handyman_id, provider_id=ctx.provider_id)
    return HandymanOut.model_validate(item)


@router.patch(
    "/me/handymen/{handyman_id}",
    response_model=HandymanOut,
    summary="Update single handyman personnel",
)
async def update_my_handyman(
    handyman_id: UUID,
    body: HandymanPatch,
    ctx: RequireProvider,
    service: Annotated[HandymanService, Depends(get_handyman_service)],
) -> HandymanOut:
    assert ctx.provider_id is not None
    updated = await service.update_handyman(
        handyman_id=handyman_id,
        provider_id=ctx.provider_id,
        patch=body.model_dump(exclude_unset=True),
    )
    return HandymanOut.model_validate(updated)


@router.delete(
    "/me/handymen/{handyman_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete handyman personnel",
)
async def delete_my_handyman(
    handyman_id: UUID,
    ctx: RequireProvider,
    service: Annotated[HandymanService, Depends(get_handyman_service)],
) -> None:
    assert ctx.provider_id is not None
    await service.delete_handyman(handyman_id, ctx.provider_id)


# ======================== Verification Document Endpoints ========================


@router.get(
    "/me/documents",
    response_model=list[ProviderDocumentOut],
    summary="List verification documents submitted by the provider",
)
async def list_my_documents(
    ctx: RequireProvider,
    service: Annotated[ProviderDocumentService, Depends(get_provider_document_service)],
) -> list[ProviderDocumentOut]:
    assert ctx.provider_id is not None
    rows = await service.list_provider_documents(ctx.provider_id)
    return [ProviderDocumentOut.model_validate(r) for r in rows]


@router.put(
    "/me/documents",
    response_model=list[ProviderDocumentOut],
    summary="Submit or replace verification documents",
)
async def submit_my_documents(
    body: ProviderDocumentsBody,
    ctx: RequireProvider,
    service: Annotated[ProviderDocumentService, Depends(get_provider_document_service)],
) -> list[ProviderDocumentOut]:
    assert ctx.provider_id is not None
    out = []
    for doc in body.documents:
        item = await service.submit_document(
            provider_id=ctx.provider_id,
            document_id=doc.document_id,
            document_image=doc.document_image,
            provider_name=body.provider_name,
            provider_email=body.provider_email,
        )
        out.append(item)
    return [ProviderDocumentOut.model_validate(r) for r in out]


@router.delete(
    "/me/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a single verification document",
)
async def delete_my_document(
    document_id: UUID,
    ctx: RequireProvider,
    service: Annotated[ProviderDocumentService, Depends(get_provider_document_service)],
) -> None:
    assert ctx.provider_id is not None
    await service.delete_document(ctx.provider_id, document_id)


# ======================== Provider Payment Method Endpoints ========================


@router.get("/me/payment-methods", response_model=list[PaymentMethodOut], operation_id="providers_list_payment_methods")
async def providers_list_payment_methods(ctx: RequireProvider, db: Annotated[AsyncSession, Depends(get_db)]):
    assert ctx.provider_id is not None
    rows = await provider_payment_methods.list_for_provider(db, ctx.provider_id)
    return [PaymentMethodOut.model_validate(r) for r in rows]


@router.put("/me/payment-methods", response_model=PaymentMethodOut, operation_id="providers_upsert_payment_method")
async def providers_upsert_payment_method(
    body: PaymentMethodWrite, ctx: RequireProvider, db: Annotated[AsyncSession, Depends(get_db)]
):
    assert ctx.provider_id is not None
    try:
        row = await provider_payment_methods.upsert(db, ctx.provider_id, body.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PaymentMethodConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return PaymentMethodOut.model_validate(row)


@router.patch(
    "/me/payment-methods/{method_id}",
    response_model=PaymentMethodOut,
    operation_id="providers_patch_payment_method",
)
async def providers_patch_payment_method(
    method_id: UUID,
    body: PaymentMethodWrite,
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    assert ctx.provider_id is not None
    try:
        row = await provider_payment_methods.upsert(
            db, ctx.provider_id, body.model_dump(exclude_unset=True), method_id=method_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PaymentMethodConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return PaymentMethodOut.model_validate(row)


@router.delete(
    "/me/payment-methods/{method_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="providers_delete_payment_method",
)
async def providers_delete_payment_method(
    method_id: UUID, ctx: RequireProvider, db: Annotated[AsyncSession, Depends(get_db)]
) -> None:
    assert ctx.provider_id is not None
    row = await provider_payment_methods.get_owned(db, ctx.provider_id, method_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment method not found")
    await provider_payment_methods.delete_owned(db, row)


# ======================== Provider Service Management Endpoints ========================


@router.get(
    "/me/services",
    response_model=list[ServiceOut],
    summary="List services owned by the authenticated provider",
)
async def list_my_services(
    ctx: RequireProvider,
    service: Annotated[ProviderServiceManagementService, Depends(get_provider_service_management)],
    include_archived: bool = Query(False, alias="includeArchived"),
) -> list[ServiceOut]:
    assert ctx.provider_id is not None
    rows = await service.list_provider_services(
        provider_id=ctx.provider_id,
        include_archived=include_archived,
    )
    return [ServiceOut.model_validate(r) for r in rows]


@router.post(
    "/me/services",
    response_model=ServiceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new service offering for the authenticated provider",
)
async def create_my_service(
    body: ServiceCreate,
    ctx: RequireProvider,
    service: Annotated[ProviderServiceManagementService, Depends(get_provider_service_management)],
) -> ServiceOut:
    assert ctx.provider_id is not None
    created = await service.create_service(
        provider_id=ctx.provider_id,
        data=body.model_dump(exclude_unset=True),
    )
    return ServiceOut.model_validate(created)


@router.get(
    "/me/services/{service_id}",
    response_model=ServiceOut,
    summary="Get single service owned by the authenticated provider",
)
async def get_my_service(
    service_id: UUID,
    ctx: RequireProvider,
    service: Annotated[ProviderServiceManagementService, Depends(get_provider_service_management)],
) -> ServiceOut:
    assert ctx.provider_id is not None
    item = await service.get_service(provider_id=ctx.provider_id, service_id=service_id)
    return ServiceOut.model_validate(item)


@router.patch(
    "/me/services/{service_id}",
    response_model=ServiceOut,
    summary="Update single service owned by the authenticated provider",
)
async def update_my_service(
    service_id: UUID,
    body: ServicePatch,
    ctx: RequireProvider,
    service: Annotated[ProviderServiceManagementService, Depends(get_provider_service_management)],
) -> ServiceOut:
    assert ctx.provider_id is not None
    updated = await service.update_service(
        provider_id=ctx.provider_id,
        service_id=service_id,
        patch=body.model_dump(exclude_unset=True),
    )
    return ServiceOut.model_validate(updated)


@router.delete(
    "/me/services/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete service owned by provider",
)
async def delete_my_service(
    service_id: UUID,
    ctx: RequireProvider,
    service: Annotated[ProviderServiceManagementService, Depends(get_provider_service_management)],
) -> None:
    assert ctx.provider_id is not None
    await service.delete_service(provider_id=ctx.provider_id, service_id=service_id)
