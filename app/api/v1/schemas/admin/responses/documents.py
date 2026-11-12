"""Response schemas for Document types and Internal documents."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentTypeResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    name: str
    active: bool
    description: str | None = None


class DocumentTypeListResponse(BaseModel):
    data: list[DocumentTypeResponseItem]


class DocumentTypeSingleResponse(BaseModel):
    data: DocumentTypeResponseItem


class AdminInternalDocumentResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    title: str
    category: str
    file_name: str = Field(serialization_alias="fileName")
    storage_path: str = Field(serialization_alias="storagePath")
    mime_type: str = Field(serialization_alias="mimeType")
    uploaded_by: UUID | None = Field(default=None, serialization_alias="uploadedBy")
    preview_url: str | None = Field(default=None, serialization_alias="previewUrl")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class AdminInternalDocumentListResponse(BaseModel):
    documents: list[AdminInternalDocumentResponseItem]


class AdminInternalDocumentSingleResponse(BaseModel):
    document: AdminInternalDocumentResponseItem

