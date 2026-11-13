"""Response schemas for Admin Bookings management."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BookingDetailResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    provider_id: UUID = Field(serialization_alias="providerId")
    customer_id: UUID | None = Field(default=None, serialization_alias="customerId")
    service_id: UUID | None = Field(default=None, serialization_alias="serviceId")
    service_name: str | None = Field(default=None, serialization_alias="serviceName")
    customer_name: str = Field(serialization_alias="customerName")
    customer_phone: str = Field(serialization_alias="customerPhone")
    customer_email: str | None = Field(default=None, serialization_alias="customerEmail")
    provider_name: str = Field(serialization_alias="providerName")
    provider_phone: str | None = Field(default=None, serialization_alias="providerPhone")
    provider_email: str | None = Field(default=None, serialization_alias="providerEmail")
    price: float
    total_amount: float = Field(serialization_alias="totalAmount")
    quantity: int
    booking_date: datetime = Field(serialization_alias="bookingDate")
    payment_completed: bool = Field(serialization_alias="paymentCompleted")
    payment_status: str = Field(serialization_alias="paymentStatus")
    payment_type: str | None = Field(default=None, serialization_alias="paymentType")
    status: str | None = None
    description: str | None = None
    booking_address: dict[str, Any] | None = Field(default=None, serialization_alias="bookingAddress")
    admin_commission: float | None = Field(default=None, serialization_alias="adminCommission")
    admin_note: str | None = Field(default=None, serialization_alias="adminNote")
    is_archived: bool = Field(serialization_alias="isArchived")
    created_at: datetime = Field(serialization_alias="createdAt")


class BookingListResponse(BaseModel):
    data: list[BookingDetailResponseItem]


class BookingSingleResponse(BaseModel):
    data: BookingDetailResponseItem


class BookingTransitionResponse(BaseModel):
    ok: bool = True
    status: str
    unchanged: bool = False
    provider_payout: float | None = Field(default=None, serialization_alias="providerPayout")
    provider_clawback: float | None = Field(default=None, serialization_alias="providerClawback")
    customer_refund: float | None = Field(default=None, serialization_alias="customerRefund")


class CommissionConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    default_commission_rate: float = Field(default=10.0, serialization_alias="defaultCommissionRate")
    min_commission_rate: float = Field(default=0.0, serialization_alias="minCommissionRate")
    max_commission_rate: float = Field(default=100.0, serialization_alias="maxCommissionRate")


class BookingWalletLedgerItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    amount: str | None = None
    is_credit: bool | None = Field(default=None, serialization_alias="isCredit")
    note: str | None = None
    type: str | None = None
    payment_type: str | None = Field(default=None, serialization_alias="paymentType")
    created_date: datetime | None = Field(default=None, serialization_alias="createdDate")


class BookingWalletLedgerResponse(BaseModel):
    data: list[BookingWalletLedgerItemResponse]


class BookingPaymentInitiateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    status: str = "success"
    checkout_url: str | None = Field(default=None, serialization_alias="checkoutUrl")
    tx_ref: str = Field(serialization_alias="txRef")
    booking_id: UUID = Field(serialization_alias="bookingId")
    amount: float
