from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.common import APIModel


class AdminMeOut(APIModel):
    admin_id: UUID = Field(serialization_alias="adminId")
    user_id: UUID = Field(serialization_alias="userId")
    email: str | None = None
    full_name: str | None = Field(default=None, serialization_alias="fullName")
    role: str
    permissions: list[str]


class AdminServiceOut(APIModel):
    id: UUID
    provider_id: UUID
    service_name: str = Field(serialization_alias="serviceName")
    description: str | None = None
    address: str | None = None
    category_id: UUID = Field(serialization_alias="categoryId")
    category_model: dict[str, Any] = Field(serialization_alias="categoryModel")
    sub_category_id: UUID = Field(serialization_alias="subCategoryId")
    sub_category_model: dict[str, Any] = Field(serialization_alias="subCategoryModel")
    type: str
    service_location_mode: str = Field(serialization_alias="serviceLocationMode")
    price: Decimal
    discount: str | None = None
    pre_payment: bool = Field(serialization_alias="prePayment")
    pre_payment_percent: Decimal | None = Field(default=None, serialization_alias="prePaymentPercent")
    service_image: list[str] = Field(serialization_alias="serviceImage")
    video: str | None = None
    location: dict[str, Any] | None = None
    duration: str | None = None
    pricing_type: str
    billing_interval: str | None = None
    billing_interval_count: int | None = None
    allows_custom_offer: bool
    approved: bool
    feature: bool
    feature_requested_status: str
    is_archived: bool | None = Field(default=None, serialization_alias="isArchived")
    status: bool
    active: bool | None = None
    created_at: datetime = Field(serialization_alias="createdAt")


class ApproveProviderServicesOut(APIModel):
    updated_count: int = Field(serialization_alias="updatedCount")
    service_ids: list[UUID] = Field(serialization_alias="serviceIds")


class FeatureDecisionBody(APIModel):
    decision: Literal["accept", "reject", "remove"]


class VerifyDocumentOut(APIModel):
    id: UUID
    provider_id: UUID = Field(serialization_alias="providerId")
    provider_name: str | None = Field(default=None, serialization_alias="providerName")
    provider_email: str | None = Field(default=None, serialization_alias="providerEmail")
    document_id: UUID | None = Field(default=None, serialization_alias="documentId")
    document_name: str | None = Field(default=None, serialization_alias="documentName")
    document_image: str | None = Field(default=None, serialization_alias="documentImage")
    sub_category_name: str | None = Field(default=None, serialization_alias="subCategoryName")
    is_verify: bool | None = Field(default=None, serialization_alias="isVerify")
    created_at: datetime | None = Field(default=None, serialization_alias="createdAt")


class RejectDocumentBody(APIModel):
    reason: str = Field(min_length=1, max_length=1000)
