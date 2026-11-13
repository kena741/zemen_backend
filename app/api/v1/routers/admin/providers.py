"""Admin Providers and operations API router."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.admin.requests.providers import (
    ArchiveProviderRequest,
    CreateProviderRequest,
    InitiateActivationPaymentRequest,
    LogPastHireRequest,
    PatchCompanyProfileRequest,
    ReconcileActivationPaymentRequest,
    SendDocumentDeliveryRequest,
    SendProviderPushRequest,
    UpdateHireNoteRequest,
    UpdateProviderProfileRequest,
    UpsertBankDetailsRequest,
    VerifyActivationPaymentRequest,
)
from app.api.v1.schemas.admin.responses.providers import (
    BankDetailsResponse,
    BankMethodItemResponse,
    CompanyItemResponse,
    CompanyProfileResponse,
    DocumentDeliveryItemResponse,
    DocumentDeliveryListResponse,
    DocumentDeliverySendResponse,
    ProviderArchiveResponse,
    ProviderBookingHistoryItemResponse,
    ProviderBookingHistoryResponse,
    ProviderCreateResponse,
    ProviderItemResponse,
    ProviderListResponse,
    ProviderSingleResponse,
    ProviderWalletHistoryResponse,
    ProviderWalletStatsResponse,
    PushReadinessResponse,
    RepeatCustomerResponse,
    ServiceHistoryStatsResponse,
    UpsertBankResponse,
)
from app.core.security.admin_deps import (
    AdminContext,
    require_admin_permission,
    require_any_admin_permission,
)
from app.core.services.admin.audit_service import AdminAuditService
from app.core.services.admin.provider_activation_service import ProviderActivationAdminService
from app.core.services.admin.provider_hire_service import ProviderHireAdminService
from app.core.services.admin.provider_service import ProviderAdminService
from app.persistence.repositories.activity_log_repo import ActivityLogRepository
from app.persistence.repositories.document_delivery_repo import DocumentDeliveryRepository
from app.persistence.repositories.provider_bank_repo import ProviderBankRepository
from app.persistence.repositories.provider_booking_repo import ProviderBookingRepository
from app.persistence.repositories.provider_company_repo import ProviderCompanyRepository
from app.persistence.repositories.provider_repo import ProviderRepository
from app.persistence.repositories.provider_wallet_repo import ProviderWalletRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/admin", tags=["admin-providers"])

Db = Annotated[AsyncSession, Depends(get_db)]
CanReadProviders = Annotated[AdminContext, Depends(require_admin_permission("providers:read"))]
CanWriteProviders = Annotated[AdminContext, Depends(require_admin_permission("providers:write"))]
CanReadBank = Annotated[
    AdminContext, Depends(require_any_admin_permission("providers:read", "finance:read"))
]
CanWriteBank = Annotated[
    AdminContext, Depends(require_any_admin_permission("providers:write", "finance:write"))
]
CanWriteBookings = Annotated[AdminContext, Depends(require_admin_permission("bookings:write"))]
CanReadFinance = Annotated[AdminContext, Depends(require_admin_permission("finance:read"))]
CanWritePush = Annotated[AdminContext, Depends(require_admin_permission("notifications:write"))]


def _get_services(
    db: AsyncSession,
) -> tuple[
    ProviderAdminService,
    ProviderHireAdminService,
    ProviderActivationAdminService,
    ProviderWalletRepository,
]:
    audit_repo = ActivityLogRepository(db)
    audit_service = AdminAuditService(audit_repo)

    prov_repo = ProviderRepository(db)
    bank_repo = ProviderBankRepository(db)
    comp_repo = ProviderCompanyRepository(db)
    deliv_repo = DocumentDeliveryRepository(db)
    booking_repo = ProviderBookingRepository(db)
    wallet_repo = ProviderWalletRepository(db)

    prov_service = ProviderAdminService(
        provider_repo=prov_repo,
        bank_repo=bank_repo,
        company_repo=comp_repo,
        delivery_repo=deliv_repo,
        audit_service=audit_service,
    )
    hire_service = ProviderHireAdminService(
        booking_repo=booking_repo,
        provider_repo=prov_repo,
        audit_service=audit_service,
    )
    activation_service = ProviderActivationAdminService(
        provider_repo=prov_repo,
        audit_service=audit_service,
    )

    return prov_service, hire_service, activation_service, wallet_repo


@router.get(
    "/providers",
    response_model=ProviderListResponse,
    operation_id="admin_providers_list",
    summary="List all providers",
)
async def list_providers(
    _: CanReadProviders,
    db: Db,
    include_archived: bool = Query(default=True, alias="includeArchived"),
) -> ProviderListResponse:
    prov_service, _, _, _ = _get_services(db)
    items = await prov_service.list_providers(include_archived=include_archived)
    return ProviderListResponse(
        data=[ProviderItemResponse.model_validate(p) for p in items]
    )


@router.get(
    "/providers/service-counts",
    response_model=dict[str, int],
    operation_id="admin_providers_service_counts",
    summary="Count active services by provider",
)
async def count_services_by_provider(_: CanReadProviders, db: Db) -> dict[str, int]:
    prov_service, _, _, _ = _get_services(db)
    return await prov_service.count_services_by_provider()


@router.post(
    "/providers",
    response_model=ProviderCreateResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_providers_create",
    summary="Create a new provider",
)
async def create_provider(
    body: CreateProviderRequest,
    ctx: CanWriteProviders,
    db: Db,
) -> ProviderCreateResponse:
    prov_service, _, _, _ = _get_services(db)
    domain, temp_pwd, sms = await prov_service.create_provider(
        first_name=body.first_name,
        last_name=body.last_name,
        email=body.email,
        phone=body.phone,
        country_code=body.country_code,
        password=body.password,
        ctx=ctx,
    )
    return ProviderCreateResponse(
        data=ProviderItemResponse.model_validate(domain),
        temporary_password=temp_pwd,
        sms=sms,
    )


@router.get(
    "/providers/{provider_id}",
    response_model=ProviderSingleResponse,
    operation_id="admin_providers_get_by_id",
    summary="Get provider by ID",
)
async def get_provider(
    provider_id: UUID,
    _: CanReadProviders,
    db: Db,
) -> ProviderSingleResponse:
    prov_service, _, _, _ = _get_services(db)
    domain = await prov_service.get_provider(provider_id)
    return ProviderSingleResponse(data=ProviderItemResponse.model_validate(domain))


@router.put(
    "/providers/{provider_id}",
    response_model=ProviderSingleResponse,
    operation_id="admin_providers_update_profile",
    summary="Update provider profile fields",
)
async def update_provider_profile(
    provider_id: UUID,
    body: UpdateProviderProfileRequest,
    ctx: CanWriteProviders,
    db: Db,
) -> ProviderSingleResponse:
    prov_service, _, _, _ = _get_services(db)
    updated = await prov_service.update_provider_profile(
        provider_id=provider_id,
        payload=body.model_dump(exclude_unset=True),
        ctx=ctx,
    )
    return ProviderSingleResponse(data=ProviderItemResponse.model_validate(updated))


@router.patch(
    "/providers/{provider_id}",
    response_model=ProviderArchiveResponse,
    operation_id="admin_providers_archive_restore",
    summary="Archive or restore provider",
)
async def archive_provider(
    provider_id: UUID,
    body: ArchiveProviderRequest,
    ctx: CanWriteProviders,
    db: Db,
) -> ProviderArchiveResponse:
    prov_service, _, _, _ = _get_services(db)
    updated = await prov_service.archive_provider(
        provider_id=provider_id,
        action=body.action,
        ctx=ctx,
    )
    return ProviderArchiveResponse(ok=True, archived_at=updated.archived_at)


@router.delete(
    "/providers/{provider_id}",
    status_code=status.HTTP_200_OK,
    operation_id="admin_providers_delete",
    summary="Delete provider",
)
async def delete_provider(
    provider_id: UUID,
    ctx: CanWriteProviders,
    db: Db,
) -> dict[str, bool]:
    prov_service, _, _, _ = _get_services(db)
    await prov_service.delete_provider(provider_id, ctx=ctx)
    return {"ok": True}


# Bank details
@router.get(
    "/providers/{provider_id}/bank-details",
    response_model=BankDetailsResponse,
    operation_id="admin_providers_get_bank_details",
    summary="Get provider bank details",
)
async def get_bank_details(
    provider_id: UUID,
    _: CanReadBank,
    db: Db,
) -> BankDetailsResponse:
    prov_service, _, _, _ = _get_services(db)
    default_m, all_m = await prov_service.get_bank_details(provider_id)
    return BankDetailsResponse(
        data=BankMethodItemResponse.model_validate(default_m) if default_m else None,
        methods=[BankMethodItemResponse.model_validate(m) for m in all_m],
    )


@router.put(
    "/providers/{provider_id}/bank-details",
    response_model=UpsertBankResponse,
    operation_id="admin_providers_upsert_bank_details",
    summary="Upsert provider bank details",
)
async def upsert_bank_details(
    provider_id: UUID,
    body: UpsertBankDetailsRequest,
    ctx: CanWriteBank,
    db: Db,
) -> UpsertBankResponse:
    prov_service, _, _, _ = _get_services(db)
    res = await prov_service.upsert_bank_details(
        provider_id=provider_id,
        holder_name=body.holder_name,
        account_number=body.account_number,
        bank_name=body.bank_name,
        swift_code=body.swift_code,
        branch_city=body.branch_city,
        branch_country=body.branch_country,
        method_code=body.method_code,
        method_id=body.id,
        ctx=ctx,
    )
    return UpsertBankResponse(status="ok", id=res.id)


# Company profile
@router.get(
    "/providers/{provider_id}/company",
    response_model=CompanyProfileResponse,
    operation_id="admin_providers_get_company_profile",
    summary="Get company profile and verification",
)
async def get_company_profile(
    provider_id: UUID,
    _: CanReadProviders,
    db: Db,
) -> CompanyProfileResponse:
    prov_service, _, _, _ = _get_services(db)
    comp, verif = await prov_service.get_company_profile(provider_id)
    return CompanyProfileResponse(
        data={
            "company": CompanyItemResponse.model_validate(comp).model_dump(by_alias=True)
            if comp
            else None,
            "verification": verif,
        }
    )


@router.patch(
    "/providers/{provider_id}/company",
    response_model=CompanyProfileResponse,
    operation_id="admin_providers_patch_company_profile",
    summary="Patch company profile and verification",
)
async def patch_company_profile(
    provider_id: UUID,
    body: PatchCompanyProfileRequest,
    ctx: CanWriteProviders,
    db: Db,
) -> CompanyProfileResponse:
    prov_service, _, _, _ = _get_services(db)
    comp, verif = await prov_service.patch_company_profile(
        provider_id=provider_id,
        payload=body.model_dump(exclude_unset=True),
        ctx=ctx,
    )
    return CompanyProfileResponse(
        data={
            "company": CompanyItemResponse.model_validate(comp).model_dump(by_alias=True),
            "verification": verif,
        }
    )


# Service / Hire history
@router.get(
    "/providers/{provider_id}/bookings",
    response_model=ProviderBookingHistoryResponse,
    operation_id="admin_providers_list_bookings",
    summary="List provider hire and booking history",
)
async def list_provider_bookings(
    provider_id: UUID,
    _: CanReadProviders,
    db: Db,
) -> ProviderBookingHistoryResponse:
    _, hire_service, _, _ = _get_services(db)
    items, stats, repeat_cust = await hire_service.list_hire_history(provider_id)
    return ProviderBookingHistoryResponse(
        data=[ProviderBookingHistoryItemResponse.model_validate(i) for i in items],
        stats=ServiceHistoryStatsResponse.model_validate(stats),
        repeat_customers=[RepeatCustomerResponse.model_validate(r) for r in repeat_cust],
    )


@router.post(
    "/providers/{provider_id}/bookings",
    operation_id="admin_providers_log_past_hire",
    summary="Log past hire for provider",
)
async def log_past_hire(
    provider_id: UUID,
    body: LogPastHireRequest,
    ctx: CanWriteBookings,
    db: Db,
) -> dict[str, Any]:
    _, hire_service, _, _ = _get_services(db)
    res = await hire_service.log_past_hire(
        provider_id=provider_id,
        booking_date=body.booking_date,
        amount=body.amount,
        customer_id=body.customer_id,
        service_id=body.service_id,
        note=body.note,
        admin_note=body.admin_note,
        ctx=ctx,
    )
    return {"data": res}


@router.patch(
    "/providers/{provider_id}/bookings",
    operation_id="admin_providers_update_hire_note",
    summary="Update hire follow-up note",
)
async def update_hire_note(
    provider_id: UUID,
    body: UpdateHireNoteRequest,
    ctx: CanWriteBookings,
    db: Db,
) -> dict[str, Any]:
    _, hire_service, _, _ = _get_services(db)
    res = await hire_service.update_hire_followup_note(
        provider_id=provider_id,
        booking_id=body.booking_id,
        admin_note=body.admin_note,
        ctx=ctx,
    )
    return {"data": res}


# Wallet history
@router.get(
    "/providers/{provider_id}/wallet-transactions",
    response_model=ProviderWalletHistoryResponse,
    operation_id="admin_providers_wallet_transactions",
    summary="Get wallet transaction history for provider",
)
async def get_wallet_transactions(
    provider_id: UUID,
    _: CanReadFinance,
    db: Db,
) -> ProviderWalletHistoryResponse:
    _, _, _, wallet_repo = _get_services(db)
    rows, stats = await wallet_repo.get_wallet_history(provider_id)
    return ProviderWalletHistoryResponse(
        data=rows,
        stats=ProviderWalletStatsResponse.model_validate(stats),
    )


# Document deliveries
@router.get(
    "/providers/{provider_id}/document-deliveries",
    response_model=DocumentDeliveryListResponse,
    operation_id="admin_providers_list_document_deliveries",
    summary="List document deliveries to provider",
)
async def list_document_deliveries(
    provider_id: UUID,
    _: CanReadProviders,
    db: Db,
) -> DocumentDeliveryListResponse:
    prov_service, _, _, _ = _get_services(db)
    deliveries = await prov_service.list_document_deliveries(provider_id)
    return DocumentDeliveryListResponse(
        deliveries=[DocumentDeliveryItemResponse.model_validate(d) for d in deliveries]
    )


@router.post(
    "/providers/{provider_id}/document-deliveries",
    response_model=DocumentDeliverySendResponse,
    operation_id="admin_providers_send_document_delivery",
    summary="Send document delivery to provider",
)
async def send_document_delivery(
    provider_id: UUID,
    body: SendDocumentDeliveryRequest,
    ctx: CanWriteProviders,
    db: Db,
) -> DocumentDeliverySendResponse:
    prov_service, _, _, _ = _get_services(db)
    delivery, push_res = await prov_service.send_document_delivery(
        provider_id=provider_id,
        document_id=body.document_id,
        note=body.note,
        ctx=ctx,
    )
    return DocumentDeliverySendResponse(
        delivery=DocumentDeliveryItemResponse.model_validate(delivery),
        push=push_res,
    )


# Push readiness & send
@router.get(
    "/push/providers/{provider_id}",
    response_model=PushReadinessResponse,
    operation_id="admin_providers_push_readiness",
    summary="Check provider push notification readiness",
)
async def get_push_readiness(
    provider_id: UUID,
    _: CanWritePush,
    db: Db,
) -> PushReadinessResponse:
    prov_service, _, _, _ = _get_services(db)
    res = await prov_service.get_push_readiness(provider_id)
    return PushReadinessResponse.model_validate(res)


@router.post(
    "/push/providers/{provider_id}",
    operation_id="admin_providers_send_push",
    summary="Send push notification to single provider",
)
async def send_provider_push(
    provider_id: UUID,
    body: SendProviderPushRequest,
    ctx: CanWritePush,
    db: Db,
) -> dict[str, Any]:
    prov_service, _, _, _ = _get_services(db)
    return await prov_service.send_provider_push(
        provider_id=provider_id,
        title=body.title,
        body=body.body,
        route=body.route,
        ctx=ctx,
    )


# Activation payments
@router.post(
    "/activate-payment",
    operation_id="admin_providers_activate_payment",
    summary="Initiate or mark provider activation payment",
)
async def activate_payment(
    body: InitiateActivationPaymentRequest,
    ctx: CanWriteProviders,
    db: Db,
) -> dict[str, Any]:
    _, _, act_service, _ = _get_services(db)
    return await act_service.initiate_activation(
        provider_id=body.provider_id,
        mode=body.mode,
        fee_amount=body.fee_amount,
        tx_ref=body.tx_ref,
        note=body.note,
        ctx=ctx,
    )


@router.post(
    "/activate-payment/verify",
    operation_id="admin_providers_verify_activation",
    summary="Verify provider activation payment",
)
async def verify_activation_payment(
    body: VerifyActivationPaymentRequest,
    ctx: CanWriteProviders,
    db: Db,
) -> dict[str, Any]:
    _, _, act_service, _ = _get_services(db)
    return await act_service.verify_activation(provider_id=body.provider_id, ctx=ctx)


@router.post(
    "/activate-payment/reconcile",
    operation_id="admin_providers_reconcile_activation",
    summary="Reconcile provider activation payment",
)
async def reconcile_activation_payment(
    body: ReconcileActivationPaymentRequest,
    ctx: CanWriteProviders,
    db: Db,
) -> dict[str, Any]:
    _, _, act_service, _ = _get_services(db)
    return await act_service.reconcile_activation(
        provider_id=body.provider_id,
        tx_ref=body.tx_ref,
        fee_amount=body.fee_amount,
        note=body.note,
        ctx=ctx,
    )
