"""Response schemas for Admin Verification."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VerifyDocumentItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    provider_id: UUID = Field(serialization_alias="providerId")
    created_at: datetime = Field(serialization_alias="createdAt")
    provider_name: str | None = Field(default=None, serialization_alias="providerName")
    provider_email: str | None = Field(default=None, serialization_alias="providerEmail")
    document_id: UUID | None = Field(default=None, serialization_alias="documentId")
    document_image: str | None = Field(default=None, serialization_alias="documentImage")
    is_verify: bool | None = Field(default=None, serialization_alias="isVerify")
    document_name: str | None = Field(default=None, serialization_alias="documentName")
    sub_category_name: str | None = Field(default=None, serialization_alias="subCategoryName")


class VerifyDocumentListResponse(BaseModel):
    data: list[VerifyDocumentItemResponse]


class VerifyDocumentSingleResponse(BaseModel):
    data: VerifyDocumentItemResponse


class NavPendingCountResponse(BaseModel):
    counts: dict[str, int]
