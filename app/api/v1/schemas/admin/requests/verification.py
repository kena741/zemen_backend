"""Request schemas for Admin Verification."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RejectVerificationDocumentRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    rejection_reason: str = Field(alias="rejectionReason")
    provider_name: str | None = Field(default=None, alias="providerName")
    document_name: str | None = Field(default=None, alias="documentName")


class UploadVerificationDocumentRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    document_id: UUID = Field(alias="documentId")
    document_image: str = Field(alias="documentImage")
