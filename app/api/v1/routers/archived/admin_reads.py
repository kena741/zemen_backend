"""Admin list/detail reads (Plan 6c). Permissions mirror lolelink-admin page access."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.admin_reads import (
    AdminBookingOut,
    AdminCustomerOut,
    AdminProviderOut,
    AdminServiceListItem,
    AdminWithdrawalDetail,
    AdminWithdrawalOut,
    DashboardSummary,
    PaymentMethodOut,
    ReconciliationReport,
)
from app.api.v1.schemas.common import Page, PageMeta
from app.core.security.admin_deps import AdminContext, RequireAdmin, require_admin_permission
from app.core.services import admin_reads, finance_reconciliation
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/admin", tags=["Admin"])

Db = Annotated[AsyncSession, Depends(get_db)]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]

BookingStatus = Literal[
    "pending", "accepted", "rejected", "on_the_way", "in_progress", "hold",
    "completed", "pending_extra_payment", "pending_approval", "admin_paid",
]
PaymentStatus = Literal[
    "pending_payment", "payment_approved_by_admin", "payment_rejected_by_admin",
    "payment_completed", "payment_cancelled",
]
WithdrawalStatus = Literal["pending", "approved", "rejected", "completed"]
FeatureStatus = Literal["none", "pending", "rejected", "accepted"]


def _perm(p: str):
    return Annotated[AdminContext, Depends(require_admin_permission(p))]


def _with(model, item: dict, *extra: str):
    out = model.model_validate(item["row"])
    return out.model_copy(update={k: item[k] for k in extra})


@router.get("/dashboard/summary", response_model=DashboardSummary, operation_id="admin_dashboard_summary")
async def admin_dashboard_summary(ctx: RequireAdmin, db: Db) -> DashboardSummary:
    return DashboardSummary.model_validate(await admin_reads.dashboard_summary(db, ctx.can))


@router.get("/customers", response_model=Page[AdminCustomerOut], operation_id="admin_list_customers")
async def admin_list_customers(
    _ctx: _perm("customers:read"),
    db: Db,
    search: str | None = Query(None, max_length=100),
    include_archived: bool = Query(False, alias="includeArchived"),
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[AdminCustomerOut]:
    items = await admin_reads.list_customers(
        db, search=search, include_archived=include_archived, limit=limit, offset=offset
    )
    return Page(
        items=[_with(AdminCustomerOut, i, "booking_count", "last_booking_at", "is_provider") for i in items],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.get("/providers", response_model=Page[AdminProviderOut], operation_id="admin_list_providers")
async def admin_list_providers(
    _ctx: _perm("providers:read"),
    db: Db,
    search: str | None = Query(None, max_length=100),
    active: bool | None = None,
    include_archived: bool = Query(False, alias="includeArchived"),
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[AdminProviderOut]:
    rows = await admin_reads.list_providers(
        db, search=search, active=active, include_archived=include_archived, limit=limit, offset=offset
    )
    return Page(
        items=[AdminProviderOut.model_validate(p).model_copy(update={"service_count": n}) for p, n in rows],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.get("/providers/{provider_id}", response_model=AdminProviderOut, operation_id="admin_get_provider")
async def admin_get_provider(provider_id: UUID, _ctx: _perm("providers:read"), db: Db) -> AdminProviderOut:
    found = await admin_reads.get_provider(db, provider_id)
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    provider, n = found
    return AdminProviderOut.model_validate(provider).model_copy(update={"service_count": n})


@router.get("/services", response_model=Page[AdminServiceListItem], operation_id="admin_list_services")
async def admin_list_services(
    _ctx: _perm("services:read"),
    db: Db,
    provider_id: UUID | None = Query(None, alias="providerId"),
    include_archived: bool = Query(False, alias="includeArchived"),
    approved: bool | None = None,
    feature_status: FeatureStatus | None = Query(None, alias="featureStatus"),
    search: str | None = Query(None, max_length=100),
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[AdminServiceListItem]:
    items = await admin_reads.list_services(
        db,
        provider_id=provider_id,
        include_archived=include_archived,
        approved=approved,
        feature_status=feature_status,
        search=search,
        limit=limit,
        offset=offset,
    )
    extras = (
        "provider_name", "provider_location", "feature_request_paid",
        "feature_request_paid_amount", "feature_request_transaction_id",
    )
    return Page(items=[_with(AdminServiceListItem, i, *extras) for i in items], meta=PageMeta(limit=limit, offset=offset))


@router.get("/bookings", response_model=Page[AdminBookingOut], operation_id="admin_list_bookings")
async def admin_list_bookings(
    _ctx: _perm("bookings:read"),
    db: Db,
    statuses: list[BookingStatus] | None = Query(None, alias="status"),
    payment_statuses: list[PaymentStatus] | None = Query(None, alias="paymentStatus"),
    provider_id: UUID | None = Query(None, alias="providerId"),
    customer_id: UUID | None = Query(None, alias="customerId"),
    created_from: datetime | None = Query(None, alias="from"),
    created_to: datetime | None = Query(None, alias="to"),
    include_archived: bool = Query(False, alias="includeArchived"),
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[AdminBookingOut]:
    items = await admin_reads.list_bookings(
        db,
        statuses=list(statuses) if statuses else None,
        payment_statuses=list(payment_statuses) if payment_statuses else None,
        provider_id=provider_id,
        customer_id=customer_id,
        created_from=created_from,
        created_to=created_to,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return Page(
        items=[_with(AdminBookingOut, i, "provider_name", "customer_name") for i in items],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.get("/bookings/{booking_id}", response_model=AdminBookingOut, operation_id="admin_get_booking")
async def admin_get_booking(booking_id: UUID, _ctx: _perm("bookings:read"), db: Db) -> AdminBookingOut:
    item = await admin_reads.get_booking(db, booking_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return _with(AdminBookingOut, item, "provider_name", "customer_name")


@router.get("/withdrawals", response_model=Page[AdminWithdrawalOut], operation_id="admin_list_withdrawals")
async def admin_list_withdrawals(
    _ctx: _perm("finance:read"),
    db: Db,
    withdrawal_status: WithdrawalStatus | None = Query(None, alias="status"),
    provider_id: UUID | None = Query(None, alias="providerId"),
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[AdminWithdrawalOut]:
    items = await admin_reads.list_withdrawals(
        db, status=withdrawal_status, provider_id=provider_id, limit=limit, offset=offset
    )
    return Page(items=[_with(AdminWithdrawalOut, i, "provider_name") for i in items], meta=PageMeta(limit=limit, offset=offset))


@router.get(
    "/withdrawals/{withdrawal_id}",
    response_model=AdminWithdrawalDetail,
    operation_id="admin_get_withdrawal",
    summary="Withdrawal with the provider's active payout methods (default first)",
)
async def admin_get_withdrawal(withdrawal_id: UUID, _ctx: _perm("finance:read"), db: Db) -> AdminWithdrawalDetail:
    item = await admin_reads.get_withdrawal(db, withdrawal_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Withdrawal not found")
    out = AdminWithdrawalDetail.model_validate(item["row"])
    return out.model_copy(
        update={
            "provider_name": item["provider_name"],
            "payment_methods": [PaymentMethodOut.model_validate(m) for m in item["payment_methods"]],
        }
    )


@router.get(
    "/finance/reconciliation",
    response_model=ReconciliationReport,
    operation_id="admin_finance_reconciliation",
    summary="Read-only wallet vs ledger check: duplicate credits and balance drift",
)
async def admin_finance_reconciliation(
    _ctx: _perm("finance:read"), db: Db, limit: Limit = 100
) -> ReconciliationReport:
    return ReconciliationReport.model_validate(await finance_reconciliation.reconciliation_report(db, limit=limit))
