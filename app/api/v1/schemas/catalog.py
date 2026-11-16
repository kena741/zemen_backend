from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from app.api.v1.schemas.base import MobileApiSchema
from app.api.v1.schemas.common import APIModel


class DocumentOut(MobileApiSchema):
    id: UUID
    name: str | None = None
    description: str | None = None
    active: bool


class SubCategoryDocumentOut(MobileApiSchema):
    """Mirrors the provider app's `RequiredDocumentModel` (document + requirement description)."""

    document: DocumentOut
    description: str | None = None
    is_required: bool = Field(serialization_alias="isRequired")


class CategoryOut(MobileApiSchema):
    id: UUID
    category_name: str = Field(serialization_alias="categoryName")
    image: str | None = None
    active: bool | None = None
    description: str | None = None


class SubCategoryOut(MobileApiSchema):
    id: UUID
    sub_category_name: str = Field(serialization_alias="subCategoryName")
    category_id: UUID = Field(serialization_alias="categoryId")
    is_free: bool = Field(serialization_alias="isFree")


class ServiceOut(MobileApiSchema):
    id: UUID
    provider_id: UUID
    service_name: str = Field(serialization_alias="serviceName")
    description: str | None = None
    category_id: UUID = Field(serialization_alias="categoryId")
    sub_category_id: UUID = Field(serialization_alias="subCategoryId")
    category_name: str | None = Field(default=None, serialization_alias="categoryName")
    sub_category_name: str | None = Field(default=None, serialization_alias="subCategoryName")
    provider_name: str | None = Field(default=None, serialization_alias="providerName")
    type: str = "fixed"
    price: float | Decimal
    discount: str | None = None
    feature: bool = False
    status: bool = True
    active: bool | None = True
    slug: str | None = None
    service_image: list[str] = Field(default_factory=list, serialization_alias="serviceImage")
    review_count: int | None = Field(default=0, serialization_alias="reviewCount")
    review_sum: float | Decimal | None = Field(default=0.0, serialization_alias="reviewSum")
    approved: bool = True
    allows_custom_offer: bool = False
    pricing_type: str = "fixed"
    billing_interval: str | None = None
    billing_interval_count: int | None = None
    pre_payment: bool = Field(default=False, serialization_alias="prePayment")
    pre_payment_percent: float | Decimal | None = Field(default=None, serialization_alias="prePaymentPercent")
    created_at: datetime | None = Field(default=None, serialization_alias="createdAt")
    liked_user: list[str] = Field(default_factory=list, serialization_alias="likedUser")
    position: dict | None = None
    location: dict | None = None
    duration: str | None = None
    address: str | None = None

    @field_validator("liked_user", mode="before")
    @classmethod
    def _likes(cls, value):
        return value or []


class ServiceCreate(MobileApiSchema):
    service_name: str = Field(alias="serviceName")
    description: str | None = None
    address: str | None = None
    category_id: UUID = Field(alias="categoryId")
    category_name: str | None = Field(default=None, alias="categoryName")
    sub_category_id: UUID = Field(alias="subCategoryId")
    sub_category_name: str | None = Field(default=None, alias="subCategoryName")
    type: str = "fixed"
    service_location_mode: str = Field(default="on_site", alias="serviceLocationMode")
    price: float | Decimal
    discount: str | None = None
    pre_payment: bool = Field(default=False, alias="prePayment")
    pre_payment_percent: float | Decimal | None = Field(default=None, alias="prePaymentPercent")
    service_image: list[str] = Field(default_factory=list, alias="serviceImage")
    duration: str | None = None
    position: dict | None = None
    location: dict | None = None
    allows_custom_offer: bool = Field(default=False, alias="allowsCustomOffer")
    billing_interval: str | None = Field(default=None, alias="billingInterval")
    billing_interval_count: int | None = Field(default=None, alias="billingIntervalCount")


class ServicePatch(MobileApiSchema):
    service_name: str | None = Field(default=None, alias="serviceName")
    description: str | None = None
    address: str | None = None
    category_id: UUID | None = Field(default=None, alias="categoryId")
    category_name: str | None = Field(default=None, alias="categoryName")
    sub_category_id: UUID | None = Field(default=None, alias="subCategoryId")
    sub_category_name: str | None = Field(default=None, alias="subCategoryName")
    type: str | None = None
    service_location_mode: str | None = Field(default=None, alias="serviceLocationMode")
    price: float | Decimal | None = None
    discount: str | None = None
    pre_payment: bool | None = Field(default=None, alias="prePayment")
    pre_payment_percent: float | Decimal | None = Field(default=None, alias="prePaymentPercent")
    service_image: list[str] | None = Field(default=None, alias="serviceImage")
    duration: str | None = None
    position: dict | None = None
    location: dict | None = None
    status: bool | None = None
    active: bool | None = None
    allows_custom_offer: bool | None = Field(default=None, alias="allowsCustomOffer")
    billing_interval: str | None = Field(default=None, alias="billingInterval")
    billing_interval_count: int | None = Field(default=None, alias="billingIntervalCount")


class BannerOut(MobileApiSchema):
    id: int | UUID
    banner_name: str | None = Field(default=None, serialization_alias="bannerName")
    image: str | None = None
    link: str | None = None
    active: bool | None = True
    created_at: datetime | None = Field(default=None, serialization_alias="createdAt")


class CouponOut(MobileApiSchema):
    id: int | UUID
    title: str | None = None
    code: str
    amount: float | Decimal | None = None
    min_amount: float | Decimal | None = Field(default=None, serialization_alias="minAmount")
    active: bool | None = True
    is_private: bool | None = Field(default=False, serialization_alias="isPrivate")
    is_fix: bool | None = Field(default=True, serialization_alias="isFix")
    expired_at: datetime | None = Field(default=None, serialization_alias="expiredAt")
    created_at: datetime | None = Field(default=None, serialization_alias="createdAt")


class SavedServiceDetailOut(APIModel):
    id: UUID
    service_name: str | None = Field(default=None, serialization_alias="serviceName")
    description: str | None = None
    price: float | None = None
    service_image: list[str] = Field(default_factory=list, serialization_alias="serviceImage")
    category_id: str | None = Field(default=None, serialization_alias="categoryId")
    sub_category_id: str | None = Field(default=None, serialization_alias="subCategoryId")
    category_model: dict | None = Field(default=None, serialization_alias="categoryModel")
    sub_category_model: dict | None = Field(default=None, serialization_alias="subCategoryModel")


class SavedServiceDetailWrite(APIModel):
    id: UUID | None = None
    service_name: str | None = Field(default=None, alias="serviceName")
    description: str | None = None
    price: float | None = None
    service_image: list[str] | None = Field(default=None, alias="serviceImage")
    category_id: str | None = Field(default=None, alias="categoryId")
    sub_category_id: str | None = Field(default=None, alias="subCategoryId")
    category_model: dict | None = Field(default=None, alias="categoryModel")
    sub_category_model: dict | None = Field(default=None, alias="subCategoryModel")


class SavedServicesOut(APIModel):
    customer_id: UUID = Field(serialization_alias="customerId")
    service_details_list: list[SavedServiceDetailOut] = Field(
        default_factory=list, serialization_alias="serviceDetailsList"
    )


class SavedServicesWrite(APIModel):
    service_details_list: list[SavedServiceDetailWrite] = Field(
        default_factory=list, alias="serviceDetailsList"
    )
