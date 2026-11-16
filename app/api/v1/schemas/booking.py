"""Pydantic schemas for Mobile Bookings, setOrder payloads, and status updates."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.base import MobileApiSchema


class BookingOut(MobileApiSchema):
    """Public booking response DTO matching Flutter `BookingModel.fromJson` keys."""

    id: UUID
    provider_id: UUID = Field(serialization_alias="providerId")
    customer_id: UUID | None = Field(default=None, serialization_alias="customerId")
    service_id: UUID | None = Field(default=None, serialization_alias="serviceId")
    handyman_id: UUID | None = Field(default=None, serialization_alias="handymanId")
    payment_id: UUID | None = Field(default=None, serialization_alias="paymentId")
    provider_user_id: UUID | None = Field(default=None, serialization_alias="providerUserId")
    customer_user_id: UUID | None = Field(default=None, serialization_alias="customerUserId")
    service_name: str | None = Field(default=None, serialization_alias="serviceName")
    first_name: str = Field(default="", serialization_alias="firstName")
    last_name: str = Field(default="", serialization_alias="lastName")
    email: str | None = None
    phone_number: str = Field(default="", serialization_alias="phoneNumber")
    price: float | Decimal | None = None
    discount: str | None = None
    total_amount: float | Decimal | None = Field(default=None, serialization_alias="totalAmount")
    sub_total: float | Decimal | None = Field(default=None, serialization_alias="subTotal")
    tax_list: list[Any] | dict[str, Any] = Field(default_factory=list, serialization_alias="taxList")
    quantity: int = 1
    booking_date: datetime = Field(serialization_alias="bookingDate")
    payment_completed: bool = Field(default=False, serialization_alias="paymentCompleted")
    payment_status: str = Field(default="pending", serialization_alias="paymentStatus")
    status: str | None = "pending"
    payment_type: str | None = Field(default=None, serialization_alias="paymentType")
    description: str | None = None
    service_image: str | None = Field(default=None, serialization_alias="serviceImage")
    booking_address: dict[str, Any] | None = Field(default=None, serialization_alias="bookingAddress")
    service_details: dict[str, Any] | list[Any] | None = Field(default=None, serialization_alias="serviceDetails")
    is_archived: bool = Field(default=False, serialization_alias="isArchived")
    next_cycle_due: bool = Field(default=False, serialization_alias="nextCycleDue")
    current_period_start: datetime | None = Field(default=None, serialization_alias="currentPeriodStart")
    current_period_end: datetime | None = Field(default=None, serialization_alias="currentPeriodEnd")
    next_cycle_notified_at: datetime | None = Field(default=None, serialization_alias="nextCycleNotifiedAt")
    created_at: datetime | None = Field(default=None, serialization_alias="createdAt")
    otp: str | None = None
    start_time: datetime | None = Field(default=None, serialization_alias="startTime")
    end_time: datetime | None = Field(default=None, serialization_alias="endTime")
    hold_time: list[Any] | None = Field(default=None, serialization_alias="holdTime")
    extra_charge_amount: str | None = Field(default=None, serialization_alias="extraChargeAmount")
    extra_charge_gst: bool | None = Field(default=None, serialization_alias="extraChargeGst")
    extra_charge_model: dict[str, Any] | None = Field(default=None, serialization_alias="extraChargeModel")
    post_job: bool | None = Field(default=False, serialization_alias="postJob")
    post_job_payment: bool | None = Field(default=False, serialization_alias="postJobPayment")
    pre_payment_extra_charge_payment: bool | None = Field(
        default=False, serialization_alias="prePaymentExtraChargePayment"
    )
    provider_myself: bool | None = Field(default=False, serialization_alias="providerMySelf")
    coupon: str | None = None
    reason: str | None = None
    service_proof: dict[str, Any] | None = Field(default=None, serialization_alias="serviceProof")
    service_proof_updated_at: datetime | None = Field(
        default=None, serialization_alias="serviceProofUpdatedAt"
    )
    customer_name: str | None = Field(default=None, serialization_alias="customerName")
    provider_name: str | None = Field(default=None, serialization_alias="providerName")
    handyman_name: str | None = Field(default=None, serialization_alias="handymanName")


class BookingCreate(MobileApiSchema):
    """Payload accepted by `setOrder` endpoint supporting dual camelCase and snake_case."""

    id: UUID | None = None
    provider_id: UUID = Field(alias="providerId")
    customer_id: UUID | None = Field(default=None, alias="customerId")
    service_id: UUID | None = Field(default=None, alias="serviceId")
    service_name: str | None = Field(default=None, alias="serviceName")
    service_image: str | None = Field(default=None, alias="serviceImage")
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    email: str | None = None
    phone_number: str | None = Field(default=None, alias="phoneNumber")
    country_code: str | None = Field(default=None, alias="countryCode")
    price: float | Decimal | None = None
    discount: str | None = None
    total_amount: float | Decimal | None = Field(default=None, alias="totalAmount")
    sub_total: float | Decimal | None = Field(default=None, alias="subTotal")
    tax_list: list[Any] | dict[str, Any] | None = Field(default=None, alias="taxList")
    quantity: int = 1
    booking_date: datetime | str | None = Field(default=None, alias="bookingDate")
    payment_completed: bool | None = Field(default=False, alias="paymentCompleted")
    payment_status: str | None = Field(default="pending", alias="paymentStatus")
    status: str | None = "pending"
    payment_type: str | None = Field(default=None, alias="paymentType")
    description: str | None = None
    booking_address: dict[str, Any] | None = Field(default=None, alias="bookingAddress")
    service_details: dict[str, Any] | list[Any] | None = Field(default=None, alias="serviceDetails")
    is_archived: bool | None = Field(default=False, alias="isArchived")
    handyman_id: UUID | None = Field(default=None, alias="handymanId")
    provider_myself: bool | None = Field(default=False, alias="providerMySelf")
    post_job: bool | None = Field(default=False, alias="postJob")
    post_job_payment: bool | None = Field(default=False, alias="postJobPayment")
    pre_payment_extra_charge_payment: bool | None = Field(
        default=False, alias="prePaymentExtraChargePayment"
    )
    extra_charge_amount: str | None = Field(default=None, alias="extraChargeAmount")
    extra_charge_gst: bool | None = Field(default=None, alias="extraChargeGst")
    extra_charge_model: dict[str, Any] | None = Field(default=None, alias="extraChargeModel")
    service_proof: dict[str, Any] | None = Field(default=None, alias="serviceProof")
    start_time: datetime | str | None = Field(default=None, alias="startTime")
    end_time: datetime | str | None = Field(default=None, alias="endTime")
    hold_time: list[Any] | None = Field(default=None, alias="holdTime")
    otp: str | None = None
    reason: str | None = None
    coupon: str | None = None
    current_period_start: datetime | str | None = Field(default=None, alias="currentPeriodStart")
    current_period_end: datetime | str | None = Field(default=None, alias="currentPeriodEnd")
    next_cycle_due: bool | None = Field(default=False, alias="nextCycleDue")


class MonthlyEarningsOut(MobileApiSchema):
    year: int
    month: int
    month_name: str = Field(serialization_alias="monthName")
    total_earnings: float = Field(serialization_alias="totalEarnings")
    completed_bookings_count: int = Field(serialization_alias="completedBookingsCount")


class VerifyBookingOtpBody(MobileApiSchema):
    otp: str


class ServiceProofBody(MobileApiSchema):
    service_proof: dict[str, Any] = Field(alias="serviceProof")
