"""Domain models for Document types and Admin Internal documents."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID


@dataclass
class DocumentTypeDomain:
    id: UUID
    name: str
    active: bool = True
    description: str | None = None


@dataclass
class AdminInternalDocumentDomain:
    id: UUID
    title: str
    file_name: str
    storage_path: str
    category: str = "other"
    mime_type: str = "application/pdf"
    uploaded_by: UUID | None = None
    preview_url: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
