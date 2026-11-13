"""Domain models for verify documents and admin document deliveries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class VerifyDocumentDomain:
    id: UUID
    provider_id: UUID
    created_at: datetime
    provider_name: str | None = None
    provider_email: str | None = None
    document_id: UUID | None = None
    document_image: str | None = None
    is_verify: bool | None = None
    document_name: str | None = None
    sub_category_name: str | None = None


@dataclass
class DocumentDeliveryDomain:
    id: UUID
    document_id: UUID
    recipient_type: str
    recipient_id: UUID
    sent_by: UUID | None
    sent_at: datetime
    acknowledged_at: datetime | None = None
    document_title: str | None = None
    document_category: str | None = None
    file_name: str | None = None
