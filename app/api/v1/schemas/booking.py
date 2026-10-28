from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.common import APIModel


class BookingOut(APIModel):
    """Public booking DTO — field aliases match mobile `BookingModel` JSON keys where practical."""

    id: UUID
    provider_id: UUID
    customer_id: UUID | None = None
    service_id: UUID | None = None
    handyman_id: UUID | None = None
    service_name: str | None = Field(default=None, serialization_alias="serviceName")
    first_name: str = Field(serialization_alias="firstName")
    last_name: str = Field(serialization_alias="lastName")
    email: str | None = None
    phone_number: str = Field(serialization_alias="phoneNumber")
    price: Decimal | None = None
    discount: str | None = None
    total_amount: Decimal | None = Field(default=None, serialization_alias="totalAmount")
    sub_total: Decimal | None = Field(default=None, serialization_alias="subTotal")
    quantity: int
    booking_date: datetime = Field(serialization_alias="bookingDate")
    payment_completed: bool = Field(serialization_alias="paymentCompleted")
    payment_status: str
    status: str | None = None
    payment_type: str | None = Field(default=None, serialization_alias="paymentType")
    description: str | None = None
    service_image: str | None = Field(default=None, serialization_alias="serviceImage")
    booking_address: dict | None = Field(default=None, serialization_alias="bookingAddress")
    is_archived: bool
    next_cycle_due: bool = Field(serialization_alias="nextCycleDue")
    current_period_start: datetime | None = Field(default=None, serialization_alias="currentPeriodStart")
    current_period_end: datetime | None = Field(default=None, serialization_alias="currentPeriodEnd")
    next_cycle_notified_at: datetime | None = Field(default=None, serialization_alias="nextCycleNotifiedAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    otp: str | None = None
    start_time: datetime | None = Field(default=None, serialization_alias="startTime")
    end_time: datetime | None = Field(default=None, serialization_alias="endTime")
    hold_time: list[Any] | None = Field(default=None, serialization_alias="holdTime")
    extra_charge_amount: str | None = Field(default=None, serialization_alias="extraChargeAmount")
    extra_charge_gst: bool | None = Field(default=None, serialization_alias="extraChargeGst")
    extra_charge_model: dict | None = Field(default=None, serialization_alias="extraChargeModel")
    post_job: bool | None = Field(default=None, serialization_alias="postJob")
    post_job_payment: bool | None = Field(default=None, serialization_alias="postJobPayment")
    pre_payment_extra_charge_payment: bool | None = Field(
        default=None, serialization_alias="prePaymentExtraChargePayment"
    )
    coupon: str | None = None
    reason: str | None = None
    service_proof: dict | None = None


class BookingCreate(APIModel):
    """Create an unpaid pending booking. Payment confirmation stays on Edge/Plan 4."""

    id: UUID | None = Field(default=None, description="Optional client UUID for idempotent create")
    provider_id: UUID = Field(alias="providerId")
    service_id: UUID | None = Field(default=None, alias="serviceId")
    service_name: str | None = Field(default=None, alias="serviceName")
    service_image: str | None = Field(default=None, alias="serviceImage")
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    email: str | None = None
    phone_number: str | None = Field(default=None, alias="phoneNumber")
    country_code: str | None = Field(default=None, alias="countryCode")
    price: Decimal | None = None
    discount: str | None = None
    total_amount: Decimal | None = Field(default=None, alias="totalAmount")
    sub_total: Decimal | None = Field(default=None, alias="subTotal")
    tax_list: list[Any] | dict[str, Any] | None = Field(default=None, alias="taxList")
    quantity: int = 1
    booking_date: datetime = Field(alias="bookingDate")
    description: str | None = None
    booking_address: dict[str, Any] | None = Field(default=None, alias="bookingAddress")
    service_details: dict[str, Any] | list[Any] | None = Field(default=None, alias="serviceDetails")
    payment_type: str | None = Field(default=None, alias="paymentType")
    post_job: bool | None = Field(default=False, alias="postJob")
    current_period_start: datetime | None = Field(default=None, alias="currentPeriodStart")
    current_period_end: datetime | None = Field(default=None, alias="currentPeriodEnd")
