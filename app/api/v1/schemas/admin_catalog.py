"""Admin write schemas. Field aliases match the Postgres column names lolelink-admin sends."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.common import APIModel

# --- Category ---------------------------------------------------------------------------


class CategoryCreate(APIModel):
    category_name: str = Field(min_length=1, alias="categoryName")
    image: str | None = None
    active: bool | None = True
    description: str | None = None


class CategoryPatch(APIModel):
    category_name: str | None = Field(default=None, min_length=1, alias="categoryName")
    image: str | None = None
    active: bool | None = None
    description: str | None = None


# --- Sub-category -----------------------------------------------------------------------


class SubCategoryCreate(APIModel):
    sub_category_name: str = Field(min_length=1, alias="subCategoryName")
    category_id: UUID = Field(alias="categoryId")
    is_free: bool = Field(default=False, alias="isFree")
    document_ids: list[UUID] = Field(default_factory=list, alias="documentIds")


class SubCategoryPatch(APIModel):
    sub_category_name: str | None = Field(default=None, min_length=1, alias="subCategoryName")
    category_id: UUID | None = Field(default=None, alias="categoryId")
    is_free: bool | None = Field(default=None, alias="isFree")
    document_ids: list[UUID] | None = Field(
        default=None,
        alias="documentIds",
        description="When present, replaces the required-document links for this sub-category.",
    )


class AdminSubCategoryOut(APIModel):
    id: UUID
    sub_category_name: str = Field(serialization_alias="subCategoryName")
    category_id: UUID = Field(serialization_alias="categoryId")
    is_free: bool = Field(serialization_alias="isFree")
    document_ids: list[UUID] = Field(default_factory=list, serialization_alias="documentIds")


# --- Coupon -----------------------------------------------------------------------------


class CouponCreate(APIModel):
    title: str | None = None
    code: str = Field(min_length=1)
    amount: Decimal = Field(ge=0)
    min_amount: Decimal | None = Field(default=None, ge=0, alias="minAmount")
    active: bool = True
    is_private: bool = Field(default=False, alias="isPrivate")
    is_fix: bool = Field(default=False, alias="isFix")
    expired_at: datetime | None = Field(default=None, alias="expiredAt")


class CouponPatch(APIModel):
    title: str | None = None
    code: str | None = Field(default=None, min_length=1)
    amount: Decimal | None = Field(default=None, ge=0)
    min_amount: Decimal | None = Field(default=None, ge=0, alias="minAmount")
    active: bool | None = None
    is_private: bool | None = Field(default=None, alias="isPrivate")
    is_fix: bool | None = Field(default=None, alias="isFix")
    expired_at: datetime | None = Field(default=None, alias="expiredAt")


class AdminCouponOut(APIModel):
    id: int
    created_at: datetime | None = None
    title: str | None = None
    code: str | None = None
    amount: Decimal | None = None
    min_amount: Decimal | None = Field(default=None, serialization_alias="minAmount")
    active: bool | None = None
    is_private: bool | None = Field(default=None, serialization_alias="isPrivate")
    is_fix: bool | None = Field(default=None, serialization_alias="isFix")
    expired_at: datetime | None = Field(default=None, serialization_alias="expiredAt")


# --- Country tax ------------------------------------------------------------------------

TaxType = Literal["percentage", "fixed"]


class TaxCreate(APIModel):
    country: str = Field(min_length=1)
    name: str = Field(min_length=1)
    value: Decimal = Field(ge=0)
    active: bool = False
    type: TaxType = "percentage"


class TaxPatch(APIModel):
    country: str | None = Field(default=None, min_length=1)
    name: str | None = Field(default=None, min_length=1)
    value: Decimal | None = Field(default=None, ge=0)
    active: bool | None = None
    type: TaxType | None = None


class AdminTaxOut(APIModel):
    id: int
    created_at: datetime | None = None
    country: str | None = None
    name: str | None = None
    value: Decimal | None = None
    active: bool | None = None
    type: str | None = None
    is_fix: bool | None = Field(default=None, serialization_alias="isFix")


# --- Handyman ---------------------------------------------------------------------------


class AdminHandymanCreate(APIModel):
    provider_id: UUID = Field(alias="providerId")
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    email: str | None = None
    phone_number: str | None = Field(default=None, alias="phoneNumber")
    user_name: str | None = Field(default=None, alias="userName")
    user_type: str | None = Field(default=None, alias="userType")
    category: str | None = None
    sub_category: str | None = Field(default=None, alias="subCategory")
    category_id: UUID | None = Field(default=None, alias="categoryId")
    sub_category_id: UUID | None = Field(default=None, alias="subCategoryId")
    profile_image: str | None = Field(default=None, alias="profileImage")
    country_code: str | None = Field(default=None, alias="countryCode")
    address: str | None = None
    active: bool | None = True
    is_active: bool | None = Field(default=True, alias="isActive")
    slug: str | None = None


class AdminHandymanPatch(APIModel):
    provider_id: UUID | None = Field(default=None, alias="providerId")
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    email: str | None = None
    phone_number: str | None = Field(default=None, alias="phoneNumber")
    user_name: str | None = Field(default=None, alias="userName")
    user_type: str | None = Field(default=None, alias="userType")
    category: str | None = None
    sub_category: str | None = Field(default=None, alias="subCategory")
    category_id: UUID | None = Field(default=None, alias="categoryId")
    sub_category_id: UUID | None = Field(default=None, alias="subCategoryId")
    profile_image: str | None = Field(default=None, alias="profileImage")
    country_code: str | None = Field(default=None, alias="countryCode")
    address: str | None = None
    active: bool | None = None
    is_active: bool | None = Field(default=None, alias="isActive")
    slug: str | None = None


class AdminHandymanOut(APIModel):
    id: UUID
    provider_id: UUID | None = None
    user_id: UUID | None = None
    first_name: str | None = Field(default=None, serialization_alias="firstName")
    last_name: str | None = Field(default=None, serialization_alias="lastName")
    email: str | None = None
    phone_number: str | None = Field(default=None, serialization_alias="phoneNumber")
    user_name: str | None = Field(default=None, serialization_alias="userName")
    user_type: str | None = Field(default=None, serialization_alias="userType")
    category: str | None = None
    sub_category: str | None = Field(default=None, serialization_alias="subCategory")
    category_id: UUID | None = Field(default=None, serialization_alias="categoryId")
    sub_category_id: UUID | None = Field(default=None, serialization_alias="subCategoryId")
    profile_image: str | None = Field(default=None, serialization_alias="profileImage")
    country_code: str | None = Field(default=None, serialization_alias="countryCode")
    address: str | None = None
    active: bool | None = None
    is_active: bool | None = Field(default=None, serialization_alias="isActive")
    slug: str | None = None
    created_at: datetime | None = Field(default=None, serialization_alias="createdAt")


# --- Notifications ----------------------------------------------------------------------


class NotificationIdsBody(APIModel):
    ids: list[UUID] | None = Field(
        default=None,
        max_length=500,
        description="Omit (mark-read only) to apply to every unread admin notification.",
    )


class NotificationBulkResult(APIModel):
    ids: list[UUID]
    read_at: datetime | None = None


# --- Services ---------------------------------------------------------------------------


class AdminServiceWrite(APIModel):
    """Fields an admin may set on `service` (create or edit)."""

    service_name: str | None = Field(default=None, min_length=1, alias="serviceName")
    description: str | None = None
    address: str | None = None
    category_id: UUID | None = Field(default=None, alias="categoryId")
    category_model: dict[str, Any] | None = Field(default=None, alias="categoryModel")
    sub_category_id: UUID | None = Field(default=None, alias="subCategoryId")
    sub_category_model: dict[str, Any] | None = Field(default=None, alias="subCategoryModel")
    type: str | None = None
    service_location_mode: str | None = Field(default=None, alias="serviceLocationMode")
    price: Decimal | None = Field(default=None, ge=0)
    discount: str | None = None
    pre_payment: bool | None = Field(default=None, alias="prePayment")
    pre_payment_percent: Decimal | None = Field(default=None, ge=0, le=100, alias="prePaymentPercent")
    status: bool | None = None
    active: bool | None = None
    slug: str | None = None
    service_image: list[str] | None = Field(default=None, alias="serviceImage")
    video: str | None = None
    location: dict[str, Any] | None = None
    duration: str | None = None
    allows_custom_offer: bool | None = None
    pricing_type: str | None = None
    billing_interval: str | None = None
    billing_interval_count: int | None = Field(default=None, ge=1)
    approved: bool | None = None
    feature: bool | None = None
    feature_requested_status: Literal["none", "pending", "rejected", "accepted"] | None = None


class AdminServiceCreate(AdminServiceWrite):
    provider_id: UUID
    service_name: str = Field(min_length=1, alias="serviceName")
    category_id: UUID = Field(alias="categoryId")
    sub_category_id: UUID = Field(alias="subCategoryId")
    price: Decimal = Field(ge=0)
