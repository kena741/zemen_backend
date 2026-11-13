"""Repository for Admin Internal Documents."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.domain.document import AdminInternalDocumentDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.admin import AdminDocument


class AdminInternalDocumentRepository(BaseRepository[AdminDocument, AdminInternalDocumentDomain]):
    model = AdminDocument

    def to_domain(self, entity: AdminDocument, preview_url: str | None = None) -> AdminInternalDocumentDomain:
        return AdminInternalDocumentDomain(
            id=entity.id,
            title=entity.title,
            category=entity.category,
            file_name=entity.file_name,
            storage_path=entity.storage_path,
            mime_type=entity.mime_type,
            uploaded_by=entity.uploaded_by,
            preview_url=preview_url,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def list_all_internal(self) -> list[AdminInternalDocumentDomain]:
        stmt = select(self.model).order_by(self.model.created_at.desc())
        res = await self.session.execute(stmt)
        return [self.to_domain(d) for d in res.scalars().all()]

