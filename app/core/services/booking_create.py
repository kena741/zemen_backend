"""Customer booking creation — unpaid draft only (Plan 3)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services import catalog_service, profile_service
from app.persistence.sqlalchemy.models import BookedService, Customer


async def create_customer_booking(
    db: AsyncSession,
    *,
    customer: Customer,
    auth_user_id: UUID,
    data: dict[str, Any],
) -> BookedService:
    provider_id: UUID = data["provider_id"]
    service_id: UUID | None = data.get("service_id")

    provider = await profile_service.get_provider_by_id(db, provider_id)
    if provider is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider not found")

    service_name = data.get("service_name")
    service_image = data.get("service_image")
    service_details = data.get("service_details")
    price = data.get("price")

    if service_id is not None:
        service = await catalog_service.get_service(db, service_id)
        if service is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Service not found")
        if service.provider_id != provider_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Service does not belong to provider",
            )
        service_name = service_name or service.service_name
        if not service_image and service.service_image:
            service_image = service.service_image[0]
        if price is None:
            price = service.price

    booking_id = data.get("id") or uuid4()
    existing = await db.get(BookedService, booking_id)
    if existing is not None:
        # Idempotent create: same customer may retry with client-generated UUID.
        if existing.customer_id != customer.id and existing.customer_user_id != auth_user_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Booking id already exists")
        return existing

    first_name = data.get("first_name") or customer.first_name
    last_name = data.get("last_name") or customer.last_name
    phone = data.get("phone_number") or customer.phone
    email = data.get("email") if data.get("email") is not None else customer.email
    country_code = data.get("country_code") or customer.country_code

    quantity = int(data.get("quantity") or 1)
    if quantity < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="quantity must be >= 1")

    tax_list = data.get("tax_list")
    if tax_list is None:
        tax_list = []

    booking_date = data["booking_date"]
    if isinstance(booking_date, str):
        booking_date = datetime.fromisoformat(booking_date.replace("Z", "+00:00"))

    now = datetime.now(UTC)
    sub_total = data.get("sub_total")
    total_amount = data.get("total_amount")
    if sub_total is not None:
        sub_total = Decimal(str(sub_total))
    if total_amount is not None:
        total_amount = Decimal(str(total_amount))
    if price is not None:
        price = Decimal(str(price))

    row = BookedService(
        id=booking_id,
        provider_id=provider_id,
        customer_id=customer.id,
        service_id=service_id,
        provider_user_id=provider.user_id,
        customer_user_id=auth_user_id,
        service_name=service_name,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone_number=phone,
        country_code=country_code,
        price=price,
        discount=data.get("discount"),
        total_amount=total_amount if total_amount is not None else sub_total,
        sub_total=sub_total if sub_total is not None else price,
        tax_list=tax_list,
        quantity=quantity,
        booking_date=booking_date,
        # Never trust client payment flags on create.
        payment_completed=False,
        payment_status="pending_payment",
        pre_payment_extra_charge_payment=False,
        post_job_payment=bool(data.get("post_job") or False),
        provider_myself=False,
        description=data.get("description"),
        service_image=service_image,
        created_at=now,
        booking_address=data.get("booking_address"),
        service_details=service_details,
        payment_type=data.get("payment_type"),
        status="pending",
        is_archived=False,
        next_cycle_due=False,
        current_period_start=data.get("current_period_start"),
        current_period_end=data.get("current_period_end"),
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row
