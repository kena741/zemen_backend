"""Request schemas for Admin Catalog and Services management."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateCategoryRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    category_name: str = Field(alias="categoryName")
    image: str | None = None
    active: bool = True
    description: str | None = None


class UpdateCategoryRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    category_name: str | None = Field(default=None, alias="categoryName")
    image: str | None = None
    active: bool | None = None
    description: str | None = None


class CreateSubCategoryRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sub_category_name: str = Field(alias="subCategoryName")
    category_id: UUID = Field(alias="categoryId")
    is_free: bool = Field(default=False, alias="isFree")
    document_ids: list[UUID] = Field(default_factory=list, alias="documentIds")


class UpdateSubCategoryRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sub_category_name: str | None = Field(default=None, alias="subCategoryName")
    category_id: UUID | None = Field(default=None, alias="categoryId")
    is_free: bool | None = Field(default=None, alias="isFree")
    document_ids: list[UUID] | None = Field(default=None, alias="documentIds")


class FeatureDecisionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    decision: Literal["accept", "reject", "unfeature"]


class SoftArchiveServiceRequest(BaseModel):
    action: Literal["archive", "unarchive"]


class ApproveByProviderRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider_id: UUID = Field(alias="providerId")

