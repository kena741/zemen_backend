from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.common import APIModel


class ProviderOut(APIModel):
    id: UUID
    user_id: UUID
    email: str | None = None
    first_name: str | None = Field(default=None, serialization_alias="firstName")
    last_name: str | None = Field(default=None, serialization_alias="lastName")
    user_name: str | None = Field(default=None, serialization_alias="userName")
    phone_number: str | None = Field(default=None, serialization_alias="phoneNumber")
    profile_image: str | None = Field(default=None, serialization_alias="profileImage")
    banner: str | None = None
    address: str | None = None
    country: str | None = None
    country_code: str | None = Field(default=None, serialization_alias="countryCode")
    currency: str | None = None
    slug: str | None = None
    active: bool
    wallet_amount: str | None = Field(default=None, serialization_alias="walletAmount")
    activation_paid: bool
    provider_type: str | None = None
    company_verification_status: str | None = None
    service_tier_max: int
    service_tier_tx_ref: str | None = None
    profession_id: str | None = Field(default=None, serialization_alias="professionId")
    category_id: str | None = Field(default=None, serialization_alias="categoryId")
    company_license_url: str | None = None
    company_rejection_reason: str | None = None
    location: Any | None = None
    created_at: datetime = Field(serialization_alias="createdAt")


class ProviderPatch(APIModel):
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    user_name: str | None = Field(default=None, alias="userName")
    phone_number: str | None = Field(default=None, alias="phoneNumber")
    email: str | None = None
    profile_image: str | None = Field(default=None, alias="profileImage")
    banner: str | None = None
    address: str | None = None
    country: str | None = None
    country_code: str | None = Field(default=None, alias="countryCode")
    currency: str | None = None
    location: Any | None = None
    social_links: Any | None = Field(default=None, alias="socialLinks")
    fcm_token: str | None = Field(default=None, alias="fcmToken")
    slug: str | None = None


class ProviderCreate(ProviderPatch):
    provider_type: Literal["individual", "company"] | None = Field(default=None, alias="providerType")


class CompanyOut(APIModel):
    id: UUID
    provider_id: UUID
    name: str
    website: str | None = None
    company_name: str | None = None
    industry: str | None = None
    company_size: str | None = None
    headquarters: str | None = None
    founded: str | None = None
    profile_bio: str | None = None
    banner_image: str | None = None


class CompanyWrite(APIModel):
    name: str | None = None
    website: str | None = None
    company_name: str | None = None
    industry: str | None = None
    company_size: str | None = None
    headquarters: str | None = None
    founded: str | None = None
    profile_bio: str | None = None
    banner_image: str | None = None


class ProviderDocumentOut(APIModel):
    id: UUID
    created_at: datetime = Field(serialization_alias="createdAt")
    provider_id: UUID = Field(serialization_alias="providerId")
    provider_name: str | None = Field(default=None, serialization_alias="providerName")
    provider_email: str | None = Field(default=None, serialization_alias="providerEmail")
    document_id: UUID | None = Field(default=None, serialization_alias="documentId")
    document_image: str | None = Field(default=None, serialization_alias="documentImage")
    is_verify: bool | None = Field(default=None, serialization_alias="isVerify")


class ProviderDocumentWrite(APIModel):
    document_id: UUID = Field(alias="documentId")
    document_image: str = Field(alias="documentImage")


class ProviderDocumentsBody(APIModel):
    documents: list[ProviderDocumentWrite]
    provider_name: str | None = Field(default=None, alias="providerName")
    provider_email: str | None = Field(default=None, alias="providerEmail")


class PaymentMethodOut(APIModel):
    id: UUID
    provider_id: UUID | None = Field(default=None, serialization_alias="providerID")
    method_type: str | None = None
    method_code: str | None = None
    method_name: str | None = None
    holder_name: str | None = Field(default=None, serialization_alias="holderName")
    account_number: str | None = Field(default=None, serialization_alias="accountNumber")
    swift_code: str | None = Field(default=None, serialization_alias="swiftCode")
    bank_name: str | None = Field(default=None, serialization_alias="bankName")
    branch_city: str | None = Field(default=None, serialization_alias="branchCity")
    branch_country: str | None = Field(default=None, serialization_alias="branchCountry")
    is_active: bool | None = None
    is_default: bool | None = None
    currency: str | None = None


class PaymentMethodWrite(APIModel):
    method_type: str | None = None
    method_code: str | None = None
    method_name: str | None = None
    holder_name: str | None = Field(default=None, alias="holderName")
    account_number: str | None = Field(default=None, alias="accountNumber")
    swift_code: str | None = Field(default=None, alias="swiftCode")
    bank_name: str | None = Field(default=None, alias="bankName")
    branch_city: str | None = Field(default=None, alias="branchCity")
    branch_country: str | None = Field(default=None, alias="branchCountry")
    is_active: bool | None = None
    is_default: bool | None = None
    currency: str | None = None
