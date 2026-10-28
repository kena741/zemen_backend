from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from app.api.v1.schemas.common import APIModel


class DocumentOut(APIModel):
    id: UUID
    name: str | None = None
    description: str | None = None
    active: bool


class SubCategoryDocumentOut(APIModel):
    """Mirrors the provider app's `RequiredDocumentModel` (document + requirement description)."""

    document: DocumentOut
    description: str | None = None
    is_required: bool = Field(serialization_alias="isRequired")


class CategoryOut(APIModel):
    id: UUID
    category_name: str = Field(serialization_alias="categoryName")
    image: str | None = None
    active: bool | None = None
    description: str | None = None


class SubCategoryOut(APIModel):
    id: UUID
    sub_category_name: str = Field(serialization_alias="subCategoryName")
    category_id: UUID = Field(serialization_alias="categoryId")
    is_free: bool = Field(serialization_alias="isFree")


class ServiceOut(APIModel):
    id: UUID
    provider_id: UUID
    service_name: str = Field(serialization_alias="serviceName")
    description: str | None = None
    category_id: UUID = Field(serialization_alias="categoryId")
    sub_category_id: UUID = Field(serialization_alias="subCategoryId")
    type: str
    price: Decimal
    discount: str | None = None
    feature: bool
    status: bool
    active: bool | None = None
    slug: str | None = None
    service_image: list[str] = Field(serialization_alias="serviceImage")
    review_count: int | None = Field(default=None, serialization_alias="reviewCount")
    review_sum: Decimal | None = Field(default=None, serialization_alias="reviewSum")
    approved: bool
    allows_custom_offer: bool
    pricing_type: str
    billing_interval: str | None = None
    billing_interval_count: int | None = None
    pre_payment: bool = Field(serialization_alias="prePayment")
    pre_payment_percent: Decimal | None = Field(default=None, serialization_alias="prePaymentPercent")
    created_at: datetime = Field(serialization_alias="createdAt")
    liked_user: list[str] = Field(default_factory=list, serialization_alias="likedUser")
    position: dict | None = None
    duration: str | None = None
    address: str | None = None

    @field_validator("liked_user", mode="before")
    @classmethod
    def _likes(cls, value):
        return value or []


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
