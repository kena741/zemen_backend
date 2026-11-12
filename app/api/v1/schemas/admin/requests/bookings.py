"""Request schemas for Admin Bookings management."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateBookingRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider_id: UUID = Field(alias="providerId")
    service_id: UUID = Field(alias="serviceId")
    customer_id: UUID = Field(alias="customerId")
    booking_date: datetime = Field(alias="bookingDate")
    quantity: int = 1
    description: str | None = None
    payment_path: Literal["pay_now", "pay_later", "wallet", "mark_paid"] = Field(
        default="pay_later", alias="paymentPath"
    )
    booking_address: dict[str, Any] | None = Field(default=None, alias="bookingAddress")
    coupon_id: int | None = Field(default=None, alias="couponId")
    coupon_code: str | None = Field(default=None, alias="couponCode")
    unit_price: float | None = Field(default=None, alias="unitPrice")


class UpdateBookingStatusRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    apply_commission: bool = Field(default=True, alias="applyCommission")
    commission_percent: float | None = Field(default=10.0, alias="commissionPercent")
    notify_provider: bool = Field(default=True, alias="notifyProvider")
    notify_customer: bool = Field(default=True, alias="notifyCustomer")


class UpdateBookingNoteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    admin_note: str | None = Field(default=None, alias="adminNote")


class InitiateBookingPaymentRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    booking_id: UUID | None = Field(default=None, alias="bookingId")
    phone_number: str | None = Field(default=None, alias="phoneNumber")


class VerifyBookingPaymentRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    booking_id: UUID = Field(alias="bookingId")


class BookingPaymentWebhookRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    event: str | None = None
    tx_ref: str | None = None
    status: str | None = None
    reference: str | None = None


class RecollectBookingPaymentRequest(BaseModel):
    mode: Literal["wallet", "mark_paid"]
