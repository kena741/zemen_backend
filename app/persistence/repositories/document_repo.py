"""Repository for Document Types."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.domain.document import DocumentTypeDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.admin import Document


class DocumentTypeRepository(BaseRepository[Document, DocumentTypeDomain]):
    model = Document

    def to_domain(self, entity: Document) -> DocumentTypeDomain:
        return DocumentTypeDomain(
            id=entity.id,
            name=entity.name or "Document",
            active=entity.active,
            description=entity.description,
        )

    async def list_all_documents(self) -> list[DocumentTypeDomain]:
        stmt = select(self.model).order_by(self.model.name.asc().nullslast())
        res = await self.session.execute(stmt)
        return [self.to_domain(d) for d in res.scalars().all()]

