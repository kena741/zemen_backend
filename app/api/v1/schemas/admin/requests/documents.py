"""Request schemas for Document types and Internal documents."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateDocumentTypeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    active: bool = True
    description: str | None = None


class UpdateDocumentTypeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID | None = None
    name: str | None = None
    active: bool | None = None
    description: str | None = None


class CreateInternalDocumentRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str
    category: Literal["agreement", "policy", "other"] = "other"
    file_name: str = Field(alias="fileName")
    storage_path: str = Field(alias="storagePath")
    mime_type: str = Field(default="application/pdf", alias="mimeType")
