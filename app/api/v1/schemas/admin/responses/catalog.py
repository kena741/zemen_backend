"""Response schemas for Admin Catalog and Services management."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CategoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    category_name: str = Field(serialization_alias="categoryName")
    image: str | None = None
    active: bool | None = True
    description: str | None = None


class CategoryListResponse(BaseModel):
    data: list[CategoryItemResponse]


class CategorySingleResponse(BaseModel):
    data: CategoryItemResponse


class SubCategoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    sub_category_name: str = Field(serialization_alias="subCategoryName")
    category_id: UUID = Field(serialization_alias="categoryId")
    category_name: str | None = Field(default=None, serialization_alias="categoryName")
    is_free: bool = Field(serialization_alias="isFree")
    document_ids: list[UUID] = Field(default_factory=list, serialization_alias="documentIds")


class SubCategoryListResponse(BaseModel):
    data: list[SubCategoryItemResponse]


class SubCategorySingleResponse(BaseModel):
    data: SubCategoryItemResponse


class ServiceItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    provider_id: UUID = Field(serialization_alias="providerId")
    service_name: str = Field(serialization_alias="serviceName")
    description: str | None = None
    address: str | None = None
    category_id: UUID = Field(serialization_alias="categoryId")
    category_name: str | None = Field(default=None, serialization_alias="categoryName")
    sub_category_id: UUID = Field(serialization_alias="subCategoryId")
    sub_category_name: str | None = Field(default=None, serialization_alias="subCategoryName")
    type: str = "fixed"
    service_location_mode: str = Field(default="on_site", serialization_alias="serviceLocationMode")
    price: float
    discount: str | None = None
    pre_payment: bool = Field(default=False, serialization_alias="prePayment")
    feature: bool = False
    status: bool = True
    active: bool | None = True
    slug: str | None = None
    service_image: list[str] = Field(default_factory=list, serialization_alias="serviceImage")
    video: str | None = None
    duration: str | None = None
    is_archived: bool | None = Field(default=False, serialization_alias="isArchived")
    approved: bool = False
    feature_requested_status: str | None = Field(default="none", serialization_alias="featureRequestedStatus")
    provider_name: str | None = Field(default=None, serialization_alias="providerName")
    provider_email: str | None = Field(default=None, serialization_alias="providerEmail")
    created_at: datetime | None = Field(default=None, serialization_alias="createdAt")


class ServiceListResponse(BaseModel):
    data: list[ServiceItemResponse]


class ServiceSingleResponse(BaseModel):
    data: ServiceItemResponse
