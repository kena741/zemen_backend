"""Pydantic schemas for Payments, Chapa verifications, and Taxes."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.base import MobileApiSchema


class ChapaVerifyBody(MobileApiSchema):
    tx_ref: str = Field(alias="txRef")
    purpose: str = "booking"
    booking_id: UUID | None = Field(default=None, alias="bookingId")


class PaymentWriteResult(MobileApiSchema):
    purpose: str | None = None
    tx_ref: str | None = Field(default=None, serialization_alias="txRef")
    booking_id: str | None = Field(default=None, serialization_alias="bookingId")
    amount: str | None = None
    created: bool | None = None
    status: str | None = None
    id: str | None = None
    reason: str | None = None
    provider_id: str | None = Field(default=None, serialization_alias="providerId")


class ActivationVerifyRequest(MobileApiSchema):
    tx_ref: str = Field(alias="txRef")
    provider_id: UUID = Field(alias="providerId")
    amount: float = 0.0


class TierPaymentVerifyRequest(MobileApiSchema):
    tx_ref: str = Field(alias="txRef")
    provider_id: UUID = Field(alias="providerId")
    amount: float = 0.0
    tier_max: int = Field(default=5, alias="tierMax")


class FeaturedPaymentVerifyRequest(MobileApiSchema):
    tx_ref: str = Field(alias="txRef")
    provider_id: UUID = Field(alias="providerId")
    service_id: UUID = Field(alias="serviceId")
    amount: float = 0.0
    user_id: UUID | None = Field(default=None, alias="userId")


class PaymentSettingsOut(MobileApiSchema):
    chapa_public_key: str = Field(serialization_alias="chapaPublicKey")
    is_test: bool = Field(serialization_alias="isTest")
    currency: str = "ETB"
    payment_methods: list[str] = Field(default_factory=list, serialization_alias="paymentMethods")


class CountryTaxOut(MobileApiSchema):
    id: int
    name: str | None = None
    country: str | None = None
    value: float
    type: str | None = "percentage"
    is_fix: bool = False
    active: bool = True


class BankOut(MobileApiSchema):
    id: str
    name: str
    code: str


class WithdrawalCreateBody(MobileApiSchema):
    amount: Decimal
    payment_method_id: UUID | None = Field(default=None, alias="paymentMethodId")
    note: str | None = None
