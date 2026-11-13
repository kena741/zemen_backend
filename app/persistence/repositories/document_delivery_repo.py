"""Repository for document deliveries and dispatches."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from app.domain.verification import DocumentDeliveryDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.admin import AdminDocument, DocumentDelivery


class DocumentDeliveryRepository(BaseRepository[DocumentDelivery, DocumentDeliveryDomain]):
    model = DocumentDelivery

    def to_domain(
        self,
        entity: DocumentDelivery,
        document_title: str | None = None,
        document_category: str | None = None,
        file_name: str | None = None,
    ) -> DocumentDeliveryDomain:
        return DocumentDeliveryDomain(
            id=entity.id,
            document_id=entity.document_id,
            recipient_type=entity.recipient_type,
            recipient_id=entity.recipient_id,
            sent_by=entity.sent_by,
            sent_at=entity.sent_at,
            acknowledged_at=entity.acknowledged_at,
            document_title=document_title,
            document_category=document_category,
            file_name=file_name,
        )

    async def list_for_recipient(
        self,
        recipient_type: str,
        recipient_id: UUID,
    ) -> list[DocumentDeliveryDomain]:
        stmt = (
            select(
                DocumentDelivery,
                AdminDocument.title.label("document_title"),
                AdminDocument.category.label("document_category"),
                AdminDocument.file_name.label("file_name"),
            )
            .outerjoin(AdminDocument, DocumentDelivery.document_id == AdminDocument.id)
            .where(
                DocumentDelivery.recipient_type == recipient_type,
                DocumentDelivery.recipient_id == recipient_id,
            )
            .order_by(DocumentDelivery.sent_at.desc())
        )
        res = await self.session.execute(stmt)
        return [
            self.to_domain(d, document_title=t, document_category=c, file_name=f)
            for d, t, c, f in res.all()
        ]

    async def create_delivery(
        self,
        document_id: UUID,
        recipient_type: str,
        recipient_id: UUID,
        sent_by: UUID | None,
    ) -> DocumentDeliveryDomain:
        now = datetime.now(timezone.utc)
        delivery = DocumentDelivery(
            id=uuid4(),
            document_id=document_id,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            sent_by=sent_by,
            sent_at=now,
        )
        self.session.add(delivery)
        await self.session.flush()

        # Fetch joined metadata
        doc_res = await self.session.execute(
            select(AdminDocument).where(AdminDocument.id == document_id)
        )
        admin_doc = doc_res.scalar_one_or_none()
        return self.to_domain(
            delivery,
            document_title=admin_doc.title if admin_doc else None,
            document_category=admin_doc.category if admin_doc else None,
            file_name=admin_doc.file_name if admin_doc else None,
        )
