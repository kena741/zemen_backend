from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.booking import BookingOut
from app.api.v1.schemas.catalog import ServiceOut
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
from app.api.v1.schemas.service_mgmt import ServiceCreate, ServiceDeleteResult, ServicePatch
from app.core.security.deps import RequireAuth, RequireProvider
from app.core.services import (
    booking_service,
    handyman_service,
    profile_service,
    provider_company,
    provider_documents,
    provider_payment_methods,
    provider_service_mgmt,
)
from app.core.services.profile_service import ProfileConflict
from app.core.services.provider_payment_methods import PaymentMethodConflict
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/providers", tags=["Providers"])


@router.post(
    "/me",
    response_model=ProviderOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="providers_create_me",
    summary="Create the authenticated user's provider profile (wallet starts at 0)",
)
async def providers_create_me(
    body: ProviderCreate,
    ctx: RequireAuth,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderOut:
    data = body.model_dump(exclude_unset=True)
    provider_type = data.pop("provider_type", None)
    try:
        row = await profile_service.create_provider(db, ctx.user_id, data, provider_type=provider_type)
    except ProfileConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ProviderOut.model_validate(row)


@router.delete(
    "/me",
    response_model=ProviderOut,
    operation_id="providers_archive_me",
    summary="Archive the authenticated provider profile (auth user delete stays on Edge)",
)
async def providers_archive_me(ctx: RequireProvider, db: Annotated[AsyncSession, Depends(get_db)]) -> ProviderOut:
    assert ctx.provider_id is not None
    row = await profile_service.get_provider_by_id(db, ctx.provider_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return ProviderOut.model_validate(await profile_service.archive_provider(db, row))


@router.get("/me/company", response_model=CompanyOut | None, operation_id="providers_get_company")
async def providers_get_company(ctx: RequireProvider, db: Annotated[AsyncSession, Depends(get_db)]) -> CompanyOut | None:
    assert ctx.provider_id is not None
    row = await provider_company.get_for_provider(db, ctx.provider_id)
    return CompanyOut.model_validate(row) if row else None


@router.put("/me/company", response_model=CompanyOut, operation_id="providers_put_company")
async def providers_put_company(
    body: CompanyWrite, ctx: RequireProvider, db: Annotated[AsyncSession, Depends(get_db)]
) -> CompanyOut:
    assert ctx.provider_id is not None
    try:
        row = await provider_company.upsert_for_provider(db, ctx.provider_id, body.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CompanyOut.model_validate(row)


@router.get("/me/documents", response_model=list[ProviderDocumentOut], operation_id="providers_list_documents")
async def providers_list_documents(ctx: RequireProvider, db: Annotated[AsyncSession, Depends(get_db)]):
    assert ctx.provider_id is not None
    rows = await provider_documents.list_for_provider(db, ctx.provider_id)
    return [ProviderDocumentOut.model_validate(r) for r in rows]


@router.put("/me/documents", response_model=list[ProviderDocumentOut], operation_id="providers_upsert_documents")
async def providers_upsert_documents(
    body: ProviderDocumentsBody, ctx: RequireProvider, db: Annotated[AsyncSession, Depends(get_db)]
):
    assert ctx.provider_id is not None
    rows = await provider_documents.upsert_documents(
        db,
        provider_id=ctx.provider_id,
        provider_name=body.provider_name,
        provider_email=body.provider_email,
        items=[d.model_dump() for d in body.documents],
    )
    return [ProviderDocumentOut.model_validate(r) for r in rows]


@router.delete("/me/documents", status_code=status.HTTP_204_NO_CONTENT, operation_id="providers_clear_documents")
async def providers_clear_documents(ctx: RequireProvider, db: Annotated[AsyncSession, Depends(get_db)]) -> None:
    assert ctx.provider_id is not None
    await provider_documents.delete_all_for_provider(db, ctx.provider_id)


@router.delete(
    "/me/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="providers_delete_document",
)
async def providers_delete_document(
    document_id: UUID, ctx: RequireProvider, db: Annotated[AsyncSession, Depends(get_db)]
) -> None:
    assert ctx.provider_id is not None
    deleted = await provider_documents.delete_by_document_id(db, ctx.provider_id, document_id)
    if deleted == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")


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


@router.get(
    "/me",
    response_model=ProviderOut,
    operation_id="providers_me",
    summary="Get authenticated provider profile",
)
async def providers_me(
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderOut:
    assert ctx.provider_id is not None
    row = await profile_service.get_provider_by_id(db, ctx.provider_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return ProviderOut.model_validate(row)


@router.patch(
    "/me",
    response_model=ProviderOut,
    operation_id="providers_patch_me",
    summary="Update authenticated provider profile (allowlisted fields)",
)
async def providers_patch_me(
    body: ProviderPatch,
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderOut:
    assert ctx.provider_id is not None
    row = await profile_service.get_provider_by_id(db, ctx.provider_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    updated = await profile_service.update_provider(
        db, row, body.model_dump(exclude_unset=True)
    )
    return ProviderOut.model_validate(updated)


@router.put(
    "/me/fcm-token",
    response_model=ProviderOut,
    operation_id="providers_put_fcm_token",
    summary="Update provider FCM token",
)
async def providers_put_fcm_token(
    body: FcmTokenBody,
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderOut:
    assert ctx.provider_id is not None
    row = await profile_service.get_provider_by_id(db, ctx.provider_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    updated = await profile_service.update_provider(
        db, row, {"fcm_token": body.fcm_token}
    )
    return ProviderOut.model_validate(updated)


@router.get(
    "/me/bookings",
    response_model=Page[BookingOut],
    operation_id="providers_me_bookings",
    summary="List bookings for the authenticated provider",
)
async def providers_me_bookings(
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_archived: bool = Query(False, alias="includeArchived"),
) -> Page[BookingOut]:
    assert ctx.provider_id is not None
    rows = await booking_service.list_bookings_for_provider(
        db,
        ctx.provider_id,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return Page(
        items=[BookingOut.model_validate(r) for r in rows],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.get(
    "/me/services",
    response_model=list[ServiceOut],
    operation_id="providers_me_services",
    summary="List services owned by the authenticated provider",
)
async def providers_me_services(
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
    include_archived: bool = Query(False, alias="includeArchived"),
) -> list[ServiceOut]:
    assert ctx.provider_id is not None
    rows = await provider_service_mgmt.list_provider_services(
        db, ctx.provider_id, include_archived=include_archived
    )
    return [ServiceOut.model_validate(r) for r in rows]


@router.post(
    "/me/services",
    response_model=ServiceOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="providers_create_service",
    summary="Create a service (approved=false until admin review)",
)
async def providers_create_service(
    body: ServiceCreate,
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServiceOut:
    assert ctx.provider_id is not None
    row = await provider_service_mgmt.create_service(
        db, provider_id=ctx.provider_id, data=body.model_dump()
    )
    return ServiceOut.model_validate(row)


@router.patch(
    "/me/services/{service_id}",
    response_model=ServiceOut,
    operation_id="providers_patch_service",
    summary="Update an owned service (cannot self-approve or self-feature)",
)
async def providers_patch_service(
    service_id: UUID,
    body: ServicePatch,
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServiceOut:
    assert ctx.provider_id is not None
    row = await provider_service_mgmt.get_owned_service(db, ctx.provider_id, service_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    updated = await provider_service_mgmt.update_service(
        db, row, body.model_dump(exclude_unset=True)
    )
    return ServiceOut.model_validate(updated)


@router.delete(
    "/me/services/{service_id}",
    response_model=ServiceDeleteResult,
    operation_id="providers_delete_service",
    summary="Delete an owned service",
)
async def providers_delete_service(
    service_id: UUID,
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServiceDeleteResult:
    assert ctx.provider_id is not None
    row = await provider_service_mgmt.get_owned_service(db, ctx.provider_id, service_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    err = await provider_service_mgmt.delete_service(db, row)
    if err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err)
    return ServiceDeleteResult(ok=True)


@router.get(
    "/me/handymen",
    response_model=list[HandymanOut],
    operation_id="providers_me_handymen",
    summary="List handymen for the authenticated provider",
)
async def providers_me_handymen(
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[HandymanOut]:
    assert ctx.provider_id is not None
    rows = await handyman_service.list_for_provider(db, ctx.provider_id)
    return [HandymanOut.model_validate(r) for r in rows]


@router.post(
    "/me/handymen",
    response_model=HandymanOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="providers_create_handyman",
)
async def providers_create_handyman(
    body: HandymanCreate,
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HandymanOut:
    assert ctx.provider_id is not None
    row = await handyman_service.create_handyman(
        db, provider_id=ctx.provider_id, data=body.model_dump()
    )
    return HandymanOut.model_validate(row)


@router.patch(
    "/me/handymen/{handyman_id}",
    response_model=HandymanOut,
    operation_id="providers_patch_handyman",
)
async def providers_patch_handyman(
    handyman_id: UUID,
    body: HandymanPatch,
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HandymanOut:
    assert ctx.provider_id is not None
    row = await handyman_service.get_owned_handyman(db, ctx.provider_id, handyman_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handyman not found")
    updated = await handyman_service.update_handyman(
        db, row, body.model_dump(exclude_unset=True)
    )
    return HandymanOut.model_validate(updated)


@router.delete(
    "/me/handymen/{handyman_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="providers_delete_handyman",
)
async def providers_delete_handyman(
    handyman_id: UUID,
    ctx: RequireProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    assert ctx.provider_id is not None
    row = await handyman_service.get_owned_handyman(db, ctx.provider_id, handyman_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handyman not found")
    await handyman_service.delete_handyman(db, row)
