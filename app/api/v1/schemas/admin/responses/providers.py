"""Response schemas for Admin Providers management."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProviderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    user_id: UUID = Field(serialization_alias="userId")
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
    location: dict[str, Any] | None = None
    slug: str | None = None
    user_type: str | None = Field(default=None, serialization_alias="userType")
    wallet_amount: str | None = Field(default="0", serialization_alias="walletAmount")
    active: bool = True
    fcm_token: str | None = Field(default=None, serialization_alias="fcmToken")
    social_links: dict[str, Any] | list[Any] = Field(default_factory=dict, serialization_alias="socialLinks")
    activation_paid: bool = Field(default=False, serialization_alias="activationPaid")
    activation_paid_at: datetime | None = Field(default=None, serialization_alias="activationPaidAt")
    activation_tx_ref: str | None = Field(default=None, serialization_alias="activationTxRef")
    provider_type: str | None = Field(default="individual", serialization_alias="providerType")
    company_verification_status: str | None = Field(default="not_submitted", serialization_alias="companyVerificationStatus")
    service_tier_max: int = Field(default=0, serialization_alias="serviceTierMax")
    service_tier_paid_at: datetime | None = Field(default=None, serialization_alias="serviceTierPaidAt")
    verified_subcategory_ids: list[UUID] = Field(default_factory=list, serialization_alias="verifiedSubcategoryIds")
    signup_source: str | None = Field(default=None, serialization_alias="signupSource")
    profession_id: str | None = Field(default=None, serialization_alias="professionId")
    category_id: str | None = Field(default=None, serialization_alias="categoryId")
    company_license_url: str | None = Field(default=None, serialization_alias="companyLicenseUrl")
    company_rejection_reason: str | None = Field(default=None, serialization_alias="companyRejectionReason")
    service_tier_tx_ref: str | None = Field(default=None, serialization_alias="serviceTierTxRef")
    admin_note: str | None = Field(default=None, serialization_alias="adminNote")
    created_at: datetime | None = Field(default=None, serialization_alias="createdAt")
    updated_at: datetime | None = Field(default=None, serialization_alias="updatedAt")
    archived_at: datetime | None = Field(default=None, serialization_alias="archivedAt")


class ProviderListResponse(BaseModel):
    data: list[ProviderItemResponse]


class ProviderSingleResponse(BaseModel):
    data: ProviderItemResponse


class ProviderCreateResponse(BaseModel):
    data: ProviderItemResponse
    temporary_password: str = Field(serialization_alias="temporaryPassword")
    sms: dict[str, Any]


class ProviderArchiveResponse(BaseModel):
    ok: bool = True
    archived_at: datetime | None = Field(default=None, serialization_alias="archivedAt")


class BankMethodItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    provider_id: UUID = Field(serialization_alias="providerId")
    method_type: str = Field(serialization_alias="methodType")
    method_code: str = Field(serialization_alias="methodCode")
    method_name: str = Field(serialization_alias="methodName")
    holder_name: str | None = Field(default=None, serialization_alias="holderName")
    account_number: str | None = Field(default=None, serialization_alias="accountNumber")
    swift_code: str | None = Field(default=None, serialization_alias="swiftCode")
    bank_name: str | None = Field(default=None, serialization_alias="bankName")
    branch_city: str | None = Field(default=None, serialization_alias="branchCity")
    branch_country: str | None = Field(default=None, serialization_alias="branchCountry")
    is_active: bool = Field(serialization_alias="isActive")
    is_default: bool = Field(serialization_alias="isDefault")
    currency: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = Field(default=None, serialization_alias="createdAt")
    updated_at: datetime | None = Field(default=None, serialization_alias="updatedAt")


class BankDetailsResponse(BaseModel):
    data: BankMethodItemResponse | None = None
    methods: list[BankMethodItemResponse] = Field(default_factory=list)


class UpsertBankResponse(BaseModel):
    status: str = "ok"
    id: UUID


class CompanyItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    provider_id: UUID = Field(serialization_alias="providerId")
    name: str
    website: str | None = None
    company_name: str | None = Field(default=None, serialization_alias="companyName")
    industry: str | None = None
    company_size: str | None = Field(default=None, serialization_alias="companySize")
    headquarters: str | None = None
    founded: str | None = None
    profile_bio: str | None = Field(default=None, serialization_alias="profileBio")
    banner_image: str | None = Field(default=None, serialization_alias="bannerImage")
    created_at: datetime | None = Field(default=None, serialization_alias="createdAt")
    updated_at: datetime | None = Field(default=None, serialization_alias="updatedAt")


class CompanyVerificationInfo(BaseModel):
    status: str | None = None
    license_url: str | None = Field(default=None, serialization_alias="licenseUrl")
    rejection_reason: str | None = Field(default=None, serialization_alias="rejectionReason")


class CompanyProfileResponse(BaseModel):
    data: dict[str, Any]


class ProviderBookingHistoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    service_name: str | None = Field(default=None, serialization_alias="serviceName")
    status: str | None = None
    payment_status: str = Field(serialization_alias="paymentStatus")
    payment_completed: bool = Field(serialization_alias="paymentCompleted")
    amount: float
    created_at: datetime = Field(serialization_alias="createdAt")
    booking_date: datetime = Field(serialization_alias="bookingDate")
    customer_id: UUID | None = Field(default=None, serialization_alias="customerId")
    customer_name: str = Field(serialization_alias="customerName")
    hired_before: bool = Field(default=False, serialization_alias="hiredBefore")
    prior_completed_count: int = Field(default=0, serialization_alias="priorCompletedCount")
    is_past_hire: bool = Field(default=False, serialization_alias="isPastHire")
    note: str | None = None
    follow_up: str | None = Field(default=None, serialization_alias="followUp")


class ServiceHistoryStatsResponse(BaseModel):
    total_bookings: int = Field(serialization_alias="totalBookings")
    completed_bookings: int = Field(serialization_alias="completedBookings")
    total_earnings: float = Field(serialization_alias="totalEarnings")
    repeat_customer_rate: float = Field(serialization_alias="repeatCustomerRate")


class RepeatCustomerResponse(BaseModel):
    customer_id: UUID = Field(serialization_alias="customerId")
    customer_name: str = Field(serialization_alias="customerName")
    hire_count: int = Field(serialization_alias="hireCount")


class ProviderBookingHistoryResponse(BaseModel):
    data: list[ProviderBookingHistoryItemResponse]
    stats: ServiceHistoryStatsResponse
    repeat_customers: list[RepeatCustomerResponse] = Field(
        default_factory=list, serialization_alias="repeatCustomers"
    )


class ProviderWalletStatsResponse(BaseModel):
    count: int
    ledger_net: float = Field(serialization_alias="ledgerNet")
    stored_wallet_amount: float = Field(serialization_alias="storedWalletAmount")
    ledger_matches_stored: bool = Field(serialization_alias="ledgerMatchesStored")


class ProviderWalletHistoryResponse(BaseModel):
    data: list[dict[str, Any]]
    stats: ProviderWalletStatsResponse


class DocumentDeliveryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    document_id: UUID = Field(serialization_alias="documentId")
    recipient_type: str = Field(serialization_alias="recipientType")
    recipient_id: UUID = Field(serialization_alias="recipientId")
    sent_by: UUID | None = Field(default=None, serialization_alias="sentBy")
    sent_at: datetime = Field(serialization_alias="sentAt")
    acknowledged_at: datetime | None = Field(default=None, serialization_alias="acknowledgedAt")
    document_title: str | None = Field(default=None, serialization_alias="documentTitle")
    document_category: str | None = Field(default=None, serialization_alias="documentCategory")
    file_name: str | None = Field(default=None, serialization_alias="fileName")


class DocumentDeliveryListResponse(BaseModel):
    deliveries: list[DocumentDeliveryItemResponse]


class DocumentDeliverySendResponse(BaseModel):
    delivery: DocumentDeliveryItemResponse
    push: dict[str, Any]


class PushReadinessResponse(BaseModel):
    fcm_registered: bool = Field(serialization_alias="fcmRegistered")
    can_send: bool = Field(serialization_alias="canSend")
    reason: str | None = None
    name: str | None = None
    sms_ready: bool = Field(serialization_alias="smsReady")
    sms_recipient: str | None = Field(default=None, serialization_alias="smsRecipient")
    debug: dict[str, Any] = Field(default_factory=dict)

