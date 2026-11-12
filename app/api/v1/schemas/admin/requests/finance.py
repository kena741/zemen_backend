"""Request schemas for Admin Finance, Payouts, and Taxes."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReviewWithdrawalRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    withdrawal_id: UUID = Field(alias="withdrawalId")
    action: Literal["approve", "reject"]
    admin_note: str | None = Field(default=None, alias="adminNote")
    rejection_reason: str | None = Field(default=None, alias="rejectionReason")


class CompleteWithdrawalRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    withdrawal_id: UUID = Field(alias="withdrawalId")
    admin_note: str | None = Field(default=None, alias="adminNote")


class ChapaTransferRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    withdrawal_id: UUID = Field(alias="withdrawalId")


class ChapaVerifyTransferRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    withdrawal_id: UUID = Field(alias="withdrawalId")


class ChapaWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    event: str | None = None
    reference: str | None = None
    status: str | None = None
    tx_ref: str | None = None


class FetchProviderPaymentMethodsRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider_ids: list[UUID] = Field(alias="providerIds")


class UpsertProviderPaymentMethodRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider_id: UUID = Field(alias="providerId")
    bank_name: str = Field(alias="bankName")
    account_number: str = Field(alias="accountNumber")
    holder_name: str | None = Field(default=None, alias="holderName")
    swift_code: str | None = Field(default=None, alias="swiftCode")
    branch_city: str | None = Field(default=None, alias="branchCity")
    branch_country: str | None = Field(default="Ethiopia", alias="branchCountry")
    is_default: bool = Field(default=True, alias="isDefault")
    method_code: str = Field(default="cbe", alias="methodCode")
    method_name: str = Field(default="Bank Transfer", alias="methodName")


class CreateCountryTaxRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    country: str
    value: float
    type: Literal["percentage", "fixed"] = "percentage"
    is_fix: bool = Field(default=False, alias="isFix")
    active: bool = True


class UpdateCountryTaxRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    country: str | None = None
    value: float | None = None
    type: Literal["percentage", "fixed"] | None = None
    is_fix: bool | None = Field(default=None, alias="isFix")
    active: bool | None = None
