"""Admin Customers API router."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.admin.requests.customers import (
    ArchiveCustomerRequest,
    CreateCustomerRequest,
    SendCustomerPushRequest,
    UpdateCustomerNoteRequest,
)
from app.api.v1.schemas.admin.responses.customers import (
    CustomerCreateResponse,
    CustomerDetailResponse,
    CustomerItemResponse,
    CustomerJobRequestItemResponse,
    CustomerJobRequestListResponse,
    CustomerListResponse,
    CustomerStatsResponse,
)
from app.api.v1.schemas.admin.responses.providers import (
    ProviderBookingHistoryItemResponse,
    ProviderItemResponse,
    ProviderSingleResponse,
    ProviderWalletHistoryResponse,
    ProviderWalletStatsResponse,
    PushReadinessResponse,
)
from app.core.security.admin_deps import (
    AdminContext,
    require_admin_permission,
)
from app.core.services.admin.audit_service import AdminAuditService
from app.core.services.admin.customer_service import CustomerAdminService
from app.persistence.repositories.activity_log_repo import ActivityLogRepository
from app.persistence.repositories.customer_repo import CustomerRepository
from app.persistence.repositories.provider_repo import ProviderRepository
from app.persistence.repositories.provider_wallet_repo import ProviderWalletRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/admin", tags=["admin-customers"])

Db = Annotated[AsyncSession, Depends(get_db)]
CanReadCustomers = Annotated[AdminContext, Depends(require_admin_permission("customers:read"))]
CanWriteCustomers = Annotated[AdminContext, Depends(require_admin_permission("customers:write"))]
CanReadFinance = Annotated[AdminContext, Depends(require_admin_permission("finance:read"))]
CanWritePush = Annotated[AdminContext, Depends(require_admin_permission("notifications:write"))]


def _get_customer_services(
    db: AsyncSession,
) -> tuple[CustomerAdminService, ProviderWalletRepository]:
    audit_repo = ActivityLogRepository(db)
    audit_service = AdminAuditService(audit_repo)
    cust_repo = CustomerRepository(db)
    prov_repo = ProviderRepository(db)
    wallet_repo = ProviderWalletRepository(db)

    service = CustomerAdminService(
        customer_repo=cust_repo,
        provider_repo=prov_repo,
        audit_service=audit_service,
    )
    return service, wallet_repo


@router.get(
    "/customers",
    response_model=CustomerListResponse,
    operation_id="admin_customers_list",
    summary="List all customers",
)
async def list_customers(
    _: CanReadCustomers,
    db: Db,
    include_archived: bool = Query(default=True, alias="includeArchived"),
) -> CustomerListResponse:
    service, _ = _get_customer_services(db)
    customers = await service.list_customers(include_archived=include_archived)
    return CustomerListResponse(
        data=[CustomerItemResponse.model_validate(c) for c in customers]
    )


@router.get(
    "/customers/resolve-booker",
    response_model=CustomerItemResponse,
    operation_id="admin_customers_resolve_booker",
    summary="Resolve default admin booker customer",
)
async def resolve_booker(
    _: CanReadCustomers,
    db: Db,
) -> CustomerItemResponse:
    service, _ = _get_customer_services(db)
    booker = await service.resolve_booker()
    return CustomerItemResponse.model_validate(booker)


@router.get(
    "/customers/by-provider/{provider_id}",
    response_model=CustomerListResponse,
    operation_id="admin_customers_list_by_provider",
    summary="List customers who booked a specific provider",
)
async def list_customers_by_provider(
    provider_id: UUID,
    _: CanReadCustomers,
    db: Db,
) -> CustomerListResponse:
    service, _ = _get_customer_services(db)
    customers = await service.list_by_provider(provider_id)
    return CustomerListResponse(
        data=[CustomerItemResponse.model_validate(c) for c in customers]
    )


@router.post(
    "/customers",
    response_model=CustomerCreateResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_customers_create",
    summary="Create customer via admin",
)
async def create_customer(
    body: CreateCustomerRequest,
    ctx: CanWriteCustomers,
    db: Db,
) -> CustomerCreateResponse:
    service, _ = _get_customer_services(db)
    domain, temp_pwd, sms = await service.create_customer(
        first_name=body.first_name,
        last_name=body.last_name,
        phone=body.phone,
        email=body.email,
        country_code=body.country_code,
        password=body.password,
        ctx=ctx,
    )
    return CustomerCreateResponse(
        data=CustomerItemResponse.model_validate(domain),
        temporary_password=temp_pwd,
        sms=sms,
    )


@router.get(
    "/customers/{customer_id}",
    response_model=CustomerDetailResponse,
    operation_id="admin_customers_get_by_id",
    summary="Get customer profile and stats",
)
async def get_customer(
    customer_id: UUID,
    _: CanReadCustomers,
    db: Db,
) -> CustomerDetailResponse:
    service, _ = _get_customer_services(db)
    customer, stats = await service.get_customer(customer_id)
    return CustomerDetailResponse(
        data=CustomerItemResponse.model_validate(customer),
        stats=CustomerStatsResponse.model_validate(stats),
    )


@router.patch(
    "/customers/{customer_id}",
    response_model=CustomerItemResponse,
    operation_id="admin_customers_archive_restore",
    summary="Archive or restore customer",
)
async def archive_customer(
    customer_id: UUID,
    body: ArchiveCustomerRequest,
    ctx: CanWriteCustomers,
    db: Db,
) -> CustomerItemResponse:
    service, _ = _get_customer_services(db)
    updated = await service.archive_customer(
        customer_id=customer_id,
        action=body.action,
        ctx=ctx,
    )
    return CustomerItemResponse.model_validate(updated)


@router.patch(
    "/customers/{customer_id}/note",
    response_model=CustomerItemResponse,
    operation_id="admin_customers_update_note",
    summary="Update customer admin note",
)
async def update_customer_note(
    customer_id: UUID,
    body: UpdateCustomerNoteRequest,
    ctx: CanWriteCustomers,
    db: Db,
) -> CustomerItemResponse:
    service, _ = _get_customer_services(db)
    updated = await service.update_customer_note(
        customer_id=customer_id,
        admin_note=body.admin_note,
        ctx=ctx,
    )
    return CustomerItemResponse.model_validate(updated)


@router.delete(
    "/customers/{customer_id}",
    status_code=status.HTTP_200_OK,
    operation_id="admin_customers_delete",
    summary="Delete customer",
)
async def delete_customer(
    customer_id: UUID,
    ctx: CanWriteCustomers,
    db: Db,
) -> dict[str, bool]:
    service, _ = _get_customer_services(db)
    await service.delete_customer(customer_id, ctx=ctx)
    return {"ok": True}


@router.post(
    "/customers/{customer_id}/convert-to-provider",
    response_model=ProviderSingleResponse,
    operation_id="admin_customers_convert_to_provider",
    summary="Convert customer to provider profile",
)
async def convert_to_provider(
    customer_id: UUID,
    ctx: CanWriteCustomers,
    db: Db,
) -> ProviderSingleResponse:
    service, _ = _get_customer_services(db)
    provider = await service.convert_to_provider(customer_id, ctx=ctx)
    return ProviderSingleResponse(data=ProviderItemResponse.model_validate(provider))


@router.get(
    "/customers/{customer_id}/bookings",
    response_model=list[ProviderBookingHistoryItemResponse],
    operation_id="admin_customers_list_bookings",
    summary="List bookings made by customer",
)
async def list_customer_bookings(
    customer_id: UUID,
    _: CanReadCustomers,
    db: Db,
) -> list[ProviderBookingHistoryItemResponse]:
    service, _ = _get_customer_services(db)
    items = await service.list_customer_bookings(customer_id)
    return [ProviderBookingHistoryItemResponse.model_validate(i) for i in items]


@router.get(
    "/customers/{customer_id}/job-requests",
    response_model=CustomerJobRequestListResponse,
    operation_id="admin_customers_list_job_requests",
    summary="List job requests submitted by customer",
)
async def list_customer_job_requests(
    customer_id: UUID,
    _: CanReadCustomers,
    db: Db,
) -> CustomerJobRequestListResponse:
    service, _ = _get_customer_services(db)
    rows = await service.list_customer_job_requests(customer_id)
    return CustomerJobRequestListResponse(
        data=[CustomerJobRequestItemResponse.model_validate(r) for r in rows]
    )


@router.get(
    "/customers/{customer_id}/wallet-transactions",
    response_model=ProviderWalletHistoryResponse,
    operation_id="admin_customers_wallet_transactions",
    summary="Get wallet transaction history for customer",
)
async def get_customer_wallet_transactions(
    customer_id: UUID,
    _: CanReadFinance,
    db: Db,
) -> ProviderWalletHistoryResponse:
    _, wallet_repo = _get_customer_services(db)
    rows, stats = await wallet_repo.get_wallet_history(customer_id)
    return ProviderWalletHistoryResponse(
        data=rows,
        stats=ProviderWalletStatsResponse.model_validate(stats),
    )


# Push readiness & send
@router.get(
    "/push/customers/{customer_id}",
    response_model=PushReadinessResponse,
    operation_id="admin_customers_push_readiness",
    summary="Check customer push notification readiness",
)
async def get_push_readiness(
    customer_id: UUID,
    _: CanWritePush,
    db: Db,
) -> PushReadinessResponse:
    service, _ = _get_customer_services(db)
    res = await service.get_push_readiness(customer_id)
    return PushReadinessResponse.model_validate(res)


@router.post(
    "/push/customers/{customer_id}",
    operation_id="admin_customers_send_push",
    summary="Send push notification to single customer",
)
async def send_customer_push(
    customer_id: UUID,
    body: SendCustomerPushRequest,
    ctx: CanWritePush,
    db: Db,
) -> dict[str, Any]:
    service, _ = _get_customer_services(db)
    return await service.send_customer_push(
        customer_id=customer_id,
        title=body.title,
        body=body.body,
        route=body.route,
        ctx=ctx,
    )

