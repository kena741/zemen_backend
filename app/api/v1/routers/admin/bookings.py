"""Admin Bookings API router."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

BookingStatus = Literal[
    "pending",
    "accepted",
    "rejected",
    "on_the_way",
    "in_progress",
    "hold",
    "completed",
    "pending_extra_payment",
    "pending_approval",
    "admin_paid",
]

from app.api.v1.schemas.admin.requests.bookings import (
    BookingPaymentWebhookRequest,
    CreateBookingRequest,
    InitiateBookingPaymentRequest,
    RecollectBookingPaymentRequest,
    UpdateBookingNoteRequest,
    UpdateBookingStatusRequest,
    VerifyBookingPaymentRequest,
)
from app.api.v1.schemas.admin.responses.bookings import (
    BookingDetailResponseItem,
    BookingListResponse,
    BookingPaymentInitiateResponse,
    BookingSingleResponse,
    BookingTransitionResponse,
    BookingWalletLedgerItemResponse,
    BookingWalletLedgerResponse,
    CommissionConfigResponse,
)
from app.core.security.admin_deps import AdminContext, require_admin_permission
from app.core.services.admin.audit_service import AdminAuditService
from app.core.services.admin.booking_service import BookingAdminService
from app.persistence.repositories.activity_log_repo import ActivityLogRepository
from app.persistence.repositories.booking_admin_repo import BookingAdminRepository
from app.persistence.repositories.customer_repo import CustomerRepository
from app.persistence.repositories.provider_repo import ProviderRepository
from app.persistence.repositories.service_repo import ServiceRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/admin", tags=["admin-bookings"])

Db = Annotated[AsyncSession, Depends(get_db)]
CanReadBookings = Annotated[AdminContext, Depends(require_admin_permission("bookings:read"))]
CanWriteBookings = Annotated[AdminContext, Depends(require_admin_permission("bookings:write"))]


def _get_booking_service(db: AsyncSession) -> BookingAdminService:
    audit_repo = ActivityLogRepository(db)
    audit_service = AdminAuditService(audit_repo)
    bkg_repo = BookingAdminRepository(db)
    prov_repo = ProviderRepository(db)
    cust_repo = CustomerRepository(db)
    srv_repo = ServiceRepository(db)
    return BookingAdminService(
        booking_repo=bkg_repo,
        provider_repo=prov_repo,
        customer_repo=cust_repo,
        service_repo=srv_repo,
        audit_service=audit_service,
    )


@router.get(
    "/bookings",
    response_model=BookingListResponse,
    operation_id="admin_bookings_list",
    summary="List all bookings with filters",
)
async def list_bookings(
    _: CanReadBookings,
    db: Db,
    statuses: list[BookingStatus] | None = Query(default=None),
    status: BookingStatus | None = Query(default=None),
    include_archived: bool = Query(default=False, alias="includeArchived"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> BookingListResponse:
    filter_statuses = [s for s in statuses] if statuses else ([status] if status else None)
    service = _get_booking_service(db)
    items = await service.list_bookings(
        statuses=filter_statuses,
        include_archived=include_archived,
        offset=offset,
        limit=limit,
    )
    return BookingListResponse(data=[BookingDetailResponseItem.model_validate(i) for i in items])


@router.get(
    "/bookings/badge-count",
    operation_id="admin_bookings_badge_count",
    summary="Count pending bookings for sidebar badge",
)
async def get_bookings_badge_count(_: CanReadBookings, db: Db) -> dict[str, int]:
    service = _get_booking_service(db)
    count = await service.count_badge()
    return {"count": count}


@router.get(
    "/bookings/commission-config",
    response_model=CommissionConfigResponse,
    operation_id="admin_bookings_commission_config",
    summary="Get admin commission rate configuration",
)
async def get_commission_config(_: CanReadBookings, db: Db) -> CommissionConfigResponse:
    service = _get_booking_service(db)
    config = await service.get_commission_config()
    return CommissionConfigResponse.model_validate(config)


@router.post(
    "/bookings",
    response_model=BookingSingleResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_bookings_create",
    summary="Create a new booking as admin",
)
async def create_booking(
    body: CreateBookingRequest,
    ctx: CanWriteBookings,
    db: Db,
) -> BookingSingleResponse:
    service = _get_booking_service(db)
    created = await service.create_booking(
        provider_id=body.provider_id,
        service_id=body.service_id,
        customer_id=body.customer_id,
        booking_date=body.booking_date,
        quantity=body.quantity,
        description=body.description,
        payment_path=body.payment_path,
        booking_address=body.booking_address,
        coupon_id=body.coupon_id,
        coupon_code=body.coupon_code,
        unit_price=body.unit_price,
        ctx=ctx,
    )
    return BookingSingleResponse(data=BookingDetailResponseItem.model_validate(created))


@router.get(
    "/bookings/{booking_id}",
    response_model=BookingSingleResponse,
    operation_id="admin_bookings_get_by_id",
    summary="Get booking details by ID",
)
async def get_booking(
    booking_id: UUID,
    _: CanReadBookings,
    db: Db,
) -> BookingSingleResponse:
    service = _get_booking_service(db)
    booking = await service.get_booking(booking_id)
    return BookingSingleResponse(data=BookingDetailResponseItem.model_validate(booking))


@router.patch(
    "/bookings/{booking_id}/status",
    response_model=BookingTransitionResponse,
    operation_id="admin_bookings_update_status",
    summary="Update booking status with commission deduction and wallet payouts",
)
async def update_booking_status(
    booking_id: UUID,
    body: UpdateBookingStatusRequest,
    ctx: CanWriteBookings,
    db: Db,
) -> BookingTransitionResponse:
    service = _get_booking_service(db)
    res = await service.update_status(
        booking_id=booking_id,
        new_status=body.status,
        apply_commission=body.apply_commission,
        commission_percent=body.commission_percent,
        notify_provider=body.notify_provider,
        notify_customer=body.notify_customer,
        ctx=ctx,
    )
    return BookingTransitionResponse(
        ok=res.ok,
        status=res.status,
        unchanged=res.unchanged,
        provider_payout=res.provider_payout,
        customer_refund=res.customer_refund,
    )


@router.patch(
    "/bookings/{booking_id}/note",
    response_model=BookingSingleResponse,
    operation_id="admin_bookings_update_note",
    summary="Update booking admin follow-up note",
)
async def update_booking_note(
    booking_id: UUID,
    body: UpdateBookingNoteRequest,
    ctx: CanWriteBookings,
    db: Db,
) -> BookingSingleResponse:
    service = _get_booking_service(db)
    updated = await service.update_note(booking_id, body.admin_note, ctx=ctx)
    return BookingSingleResponse(data=BookingDetailResponseItem.model_validate(updated))


@router.delete(
    "/bookings/{booking_id}",
    status_code=status.HTTP_200_OK,
    operation_id="admin_bookings_delete",
    summary="Delete booking and cascade related payments/notifications",
)
async def delete_booking(
    booking_id: UUID,
    ctx: CanWriteBookings,
    db: Db,
) -> dict[str, bool]:
    service = _get_booking_service(db)
    await service.delete_booking(booking_id, ctx=ctx)
    return {"ok": True}


@router.post(
    "/bookings/payment",
    response_model=BookingPaymentInitiateResponse,
    operation_id="admin_bookings_initiate_payment_body",
    summary="Initiate Chapa payment checkout for booking (payload path)",
)
async def initiate_payment_body(
    body: InitiateBookingPaymentRequest,
    ctx: CanWriteBookings,
    db: Db,
) -> BookingPaymentInitiateResponse:
    if not body.booking_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="bookingId is required",
        )
    service = _get_booking_service(db)
    res = await service.initiate_payment(body.booking_id, phone_number=body.phone_number, ctx=ctx)
    return BookingPaymentInitiateResponse.model_validate(res)


@router.post(
    "/bookings/payment/verify",
    operation_id="admin_bookings_verify_payment_body",
    summary="Verify booking payment status (payload path)",
)
async def verify_payment_body(
    body: VerifyBookingPaymentRequest,
    ctx: CanWriteBookings,
    db: Db,
) -> dict[str, Any]:
    service = _get_booking_service(db)
    return await service.verify_payment(body.booking_id, ctx=ctx)


@router.post(
    "/bookings/payment/webhook",
    operation_id="admin_bookings_payment_webhook",
    summary="Chapa payment webhook handler",
)
async def handle_payment_webhook(
    body: BookingPaymentWebhookRequest,
    db: Db,
) -> dict[str, Any]:
    if not body.tx_ref or not body.tx_ref.startswith("bkg-"):
        return {"status": "ignored"}
    # tx_ref format: bkg-<booking_hex_8>-<token>
    # Find booking by checking tx_ref in payments table or status
    service = _get_booking_service(db)
    return {"status": "success", "tx_ref": body.tx_ref}


@router.post(
    "/bookings/{booking_id}/payment",
    response_model=BookingPaymentInitiateResponse,
    operation_id="admin_bookings_initiate_payment",
    summary="Initiate Chapa payment checkout for booking",
)
async def initiate_payment(
    booking_id: UUID,
    body: InitiateBookingPaymentRequest,
    ctx: CanWriteBookings,
    db: Db,
) -> BookingPaymentInitiateResponse:
    service = _get_booking_service(db)
    res = await service.initiate_payment(booking_id, phone_number=body.phone_number, ctx=ctx)
    return BookingPaymentInitiateResponse.model_validate(res)


@router.post(
    "/bookings/{booking_id}/payment/verify",
    operation_id="admin_bookings_verify_payment",
    summary="Verify booking payment status",
)
async def verify_payment(
    booking_id: UUID,
    ctx: CanWriteBookings,
    db: Db,
) -> dict[str, Any]:
    service = _get_booking_service(db)
    return await service.verify_payment(booking_id, ctx=ctx)


@router.post(
    "/bookings/{booking_id}/recollect-payment",
    operation_id="admin_bookings_recollect_payment",
    summary="Re-collect booking payment via wallet or mark paid",
)
async def recollect_payment(
    booking_id: UUID,
    body: RecollectBookingPaymentRequest,
    ctx: CanWriteBookings,
    db: Db,
) -> dict[str, Any]:
    service = _get_booking_service(db)
    return await service.recollect_payment(booking_id, mode=body.mode, ctx=ctx)


@router.get(
    "/bookings/{booking_id}/wallet-ledger",
    response_model=BookingWalletLedgerResponse,
    operation_id="admin_bookings_wallet_ledger",
    summary="Get wallet ledger entries associated with this booking",
)
async def get_wallet_ledger(
    booking_id: UUID,
    _: CanReadBookings,
    db: Db,
) -> BookingWalletLedgerResponse:
    service = _get_booking_service(db)
    ledger = await service.get_wallet_ledger(booking_id)
    return BookingWalletLedgerResponse(
        data=[BookingWalletLedgerItemResponse.model_validate(item) for item in ledger]
    )
