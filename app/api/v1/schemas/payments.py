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


class ChapaInitializeRequest(MobileApiSchema):
    amount: float
    currency: str = "ETB"
    email: str = "customer@example.com"
    first_name: str = Field(default="Customer", alias="firstName")
    last_name: str = Field(default="User", alias="lastName")
    phone_number: str | None = Field(default=None, alias="phoneNumber")
    tx_ref: str | None = Field(default=None, alias="txRef")
    callback_url: str | None = Field(default=None, alias="callbackUrl")
    return_url: str | None = Field(default=None, alias="returnUrl")


class ChapaInitializeResponse(MobileApiSchema):
    status: str
    checkout_url: str = Field(serialization_alias="checkoutUrl")
    tx_ref: str = Field(serialization_alias="txRef")
    message: str | None = None


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


class SubscriptionPlanOut(MobileApiSchema):
    id: int
    title: str
    description: str | None = None
    price: float
    service_limit: int = Field(default=2, serialization_alias="serviceLimit")
    duration: str | None = "1 Month"
    plan_type: str = Field(default="tier", serialization_alias="planType")
    active: bool = True


class TierPurchaseInitiateRequest(MobileApiSchema):
    plan_id: int | None = Field(default=None, alias="planId")
    tier_max: int | None = Field(default=None, alias="tierMax")
    callback_url: str | None = Field(default=None, alias="callbackUrl")
    return_url: str | None = Field(default=None, alias="returnUrl")


class TierPaymentVerifyRequest(MobileApiSchema):
    tx_ref: str = Field(alias="txRef")
    provider_id: UUID | None = Field(default=None, alias="providerId")
    amount: float | None = None
    tier_max: int | None = Field(default=None, alias="tierMax")
    # Set by Next after Telebirr queryOrder succeeds; requires X-Zemen-Pay-Sig.
    skip_gateway_verify: bool = Field(default=False, alias="skipGatewayVerify")


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
    swift: str | None = None
    acct_length: int | None = Field(default=None, serialization_alias="acctLength")
    is_rtgs: bool | None = Field(default=None, serialization_alias="isRtgs")
    is_mobilemoney: bool | None = Field(default=None, serialization_alias="isMobileMoney")


class WithdrawalCreateBody(MobileApiSchema):
    amount: Decimal
    payment_method_id: UUID | None = Field(default=None, alias="paymentMethodId")
    note: str | None = None
