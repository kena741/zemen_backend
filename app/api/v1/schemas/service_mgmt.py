from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.catalog import ServiceOut
from app.api.v1.schemas.common import APIModel


class ServiceCreate(APIModel):
    service_name: str = Field(alias="serviceName")
    description: str | None = None
    address: str | None = None
    category_id: UUID = Field(alias="categoryId")
    category_model: dict[str, Any] | None = Field(default=None, alias="categoryModel")
    sub_category_id: UUID = Field(alias="subCategoryId")
    sub_category_model: dict[str, Any] | None = Field(default=None, alias="subCategoryModel")
    type: str = "fixed"
    service_location_mode: str = Field(default="onsite", alias="serviceLocationMode")
    price: Decimal
    discount: str | None = None
    pre_payment: bool = Field(default=False, alias="prePayment")
    status: bool = True
    active: bool | None = True
    slug: str | None = None
    service_image: list[str] = Field(default_factory=list, alias="serviceImage")
    location: dict[str, Any] | None = None
    duration: str | None = None
    allows_custom_offer: bool = False
    pricing_type: str = "ONE_TIME"
    billing_interval: str | None = None
    billing_interval_count: int | None = None
    pre_payment_percent: Decimal | None = Field(default=None, alias="prePaymentPercent")


class ServicePatch(APIModel):
    service_name: str | None = Field(default=None, alias="serviceName")
    description: str | None = None
    address: str | None = None
    category_id: UUID | None = Field(default=None, alias="categoryId")
    category_model: dict[str, Any] | None = Field(default=None, alias="categoryModel")
    sub_category_id: UUID | None = Field(default=None, alias="subCategoryId")
    sub_category_model: dict[str, Any] | None = Field(default=None, alias="subCategoryModel")
    type: str | None = None
    service_location_mode: str | None = Field(default=None, alias="serviceLocationMode")
    price: Decimal | None = None
    discount: str | None = None
    pre_payment: bool | None = Field(default=None, alias="prePayment")
    status: bool | None = None
    active: bool | None = None
    slug: str | None = None
    service_image: list[str] | None = Field(default=None, alias="serviceImage")
    location: dict[str, Any] | None = None
    duration: str | None = None
    allows_custom_offer: bool | None = None
    pricing_type: str | None = None
    billing_interval: str | None = None
    billing_interval_count: int | None = None
    pre_payment_percent: Decimal | None = Field(default=None, alias="prePaymentPercent")
    is_archived: bool | None = Field(default=None, alias="isArchived")


class ServiceDeleteResult(APIModel):
    ok: bool
    message: str | None = None


# Re-export for routers
__all__ = ["ServiceCreate", "ServicePatch", "ServiceDeleteResult", "ServiceOut"]
