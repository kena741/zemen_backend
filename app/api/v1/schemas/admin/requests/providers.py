"""Request schemas for Admin Providers management."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CreateProviderRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    email: EmailStr | None = None
    phone: str | None = Field(default=None, alias="phoneNumber")
    country_code: str | None = Field(default="+251", alias="countryCode")
    password: str | None = None


class UpdateProviderProfileRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    phone_number: str | None = Field(default=None, alias="phoneNumber")
    address: str | None = None
    location: dict[str, Any] | None = None
    banner: str | None = None
    profile_image: str | None = Field(default=None, alias="profileImage")
    profile_bio: str | None = Field(default=None, alias="profileBio")
    company_name: str | None = Field(default=None, alias="companyName")
    country_code: str | None = Field(default=None, alias="countryCode")
    admin_note: str | None = None


class ArchiveProviderRequest(BaseModel):
    action: Literal["archive", "restore"]


class UpsertBankDetailsRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID | None = None
    holder_name: str | None = Field(default=None, alias="holderName")
    account_number: str = Field(alias="accountNumber")
    bank_name: str | None = Field(default=None, alias="bankName")
    swift_code: str | None = Field(default=None, alias="swiftCode")
    branch_city: str | None = Field(default=None, alias="branchCity")
    branch_country: str | None = Field(default=None, alias="branchCountry")
    method_code: str | None = None


class PatchCompanyProfileRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    company_name: str | None = Field(default=None, alias="companyName")
    website: str | None = None
    industry: str | None = None
    company_size: str | None = Field(default=None, alias="companySize")
    headquarters: str | None = None
    founded: str | None = None
    profile_bio: str | None = Field(default=None, alias="profileBio")
    banner_image: str | None = Field(default=None, alias="bannerImage")
    company_verification_status: str | None = Field(default=None, alias="companyVerificationStatus")
    company_license_url: str | None = Field(default=None, alias="companyLicenseUrl")
    company_rejection_reason: str | None = Field(default=None, alias="companyRejectionReason")


class LogPastHireRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    customer_id: UUID | None = None
    service_id: UUID | None = None
    booking_date: datetime = Field(alias="bookingDate")
    amount: float
    note: str | None = None
    admin_note: str | None = None


class UpdateHireNoteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    booking_id: UUID
    admin_note: str | None = None


class SendDocumentDeliveryRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    document_id: UUID = Field(alias="documentId")
    note: str | None = None


class SendProviderPushRequest(BaseModel):
    title: str
    body: str
    route: str | None = None


class InitiateActivationPaymentRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider_id: UUID = Field(alias="providerId")
    mode: Literal["chapa", "manual"]
    fee_amount: float = Field(alias="feeAmount")
    tx_ref: str | None = Field(default=None, alias="txRef")
    note: str | None = None


class VerifyActivationPaymentRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider_id: UUID = Field(alias="providerId")


class ReconcileActivationPaymentRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider_id: UUID = Field(alias="providerId")
    tx_ref: str | None = Field(default=None, alias="txRef")
    fee_amount: float | None = Field(default=None, alias="feeAmount")
    note: str | None = None
