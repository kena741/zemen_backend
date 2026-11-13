"""Repository for Verification Documents persistence and queries."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update

from app.domain.verification import VerifyDocumentDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.admin import Document, SubCategoryDocument, VerifyDocument
from app.persistence.sqlalchemy.models.catalog import SubCategory


class VerifyDocumentRepository(BaseRepository[VerifyDocument, VerifyDocumentDomain]):
    model = VerifyDocument

    def to_domain(
        self,
        entity: VerifyDocument,
        document_name: str | None = None,
        sub_category_name: str | None = None,
    ) -> VerifyDocumentDomain:
        return VerifyDocumentDomain(
            id=entity.id,
            provider_id=entity.provider_id,
            created_at=entity.created_at,
            provider_name=entity.provider_name,
            provider_email=entity.provider_email,
            document_id=entity.document_id,
            document_image=entity.document_image,
            is_verify=entity.is_verify,
            document_name=document_name,
            sub_category_name=sub_category_name,
        )

    async def list_enriched(self) -> list[VerifyDocumentDomain]:
        """List verify documents enriched with document name and subcategory name."""
        stmt = (
            select(
                VerifyDocument,
                Document.name.label("document_name"),
                SubCategory.sub_category_name.label("sub_category_name"),
            )
            .outerjoin(Document, VerifyDocument.document_id == Document.id)
            .outerjoin(SubCategoryDocument, SubCategoryDocument.document_id == Document.id)
            .outerjoin(SubCategory, SubCategory.id == SubCategoryDocument.sub_category_id)
            .order_by(VerifyDocument.created_at.desc())
        )
        res = await self.session.execute(stmt)
        rows = res.all()
        # Deduplicate rows by verify_document.id in case of multiple subcategories
        seen: set[UUID] = set()
        items: list[VerifyDocumentDomain] = []
        for vd, doc_name, sub_cat_name in rows:
            if vd.id in seen:
                continue
            seen.add(vd.id)
            items.append(self.to_domain(vd, document_name=doc_name, sub_category_name=sub_cat_name))
        return items

    async def get_enriched_by_id(self, doc_id: UUID) -> VerifyDocumentDomain | None:
        stmt = (
            select(
                VerifyDocument,
                Document.name.label("document_name"),
                SubCategory.sub_category_name.label("sub_category_name"),
            )
            .outerjoin(Document, VerifyDocument.document_id == Document.id)
            .outerjoin(SubCategoryDocument, SubCategoryDocument.document_id == Document.id)
            .outerjoin(SubCategory, SubCategory.id == SubCategoryDocument.sub_category_id)
            .where(VerifyDocument.id == doc_id)
        )
        res = await self.session.execute(stmt)
        row = res.first()
        if not row:
            return None
        vd, doc_name, sub_cat_name = row
        return self.to_domain(vd, document_name=doc_name, sub_category_name=sub_cat_name)

    async def count_pending(self) -> int:
        stmt = select(func.count(self.model.id)).where(self.model.is_verify.is_(None))
        res = await self.session.execute(stmt)
        return int(res.scalar_one() or 0)

    async def update_verification_status(
        self,
        doc_id: UUID,
        is_verify: bool | None,
    ) -> VerifyDocumentDomain | None:
        stmt = (
            update(self.model)
            .where(self.model.id == doc_id)
            .values(is_verify=is_verify)
            .returning(self.model)
        )
        res = await self.session.execute(stmt)
        updated = res.scalar_one_or_none()
        if not updated:
            return None
        return await self.get_enriched_by_id(updated.id)

    async def approve_all_pending(self, provider_id: UUID) -> list[VerifyDocumentDomain]:
        stmt = (
            update(self.model)
            .where(self.model.provider_id == provider_id, self.model.is_verify.is_(None))
            .values(is_verify=True)
            .returning(self.model.id)
        )
        res = await self.session.execute(stmt)
        updated_ids = [row[0] for row in res.all()]
        if not updated_ids:
            return []
        # Return enriched updated items
        items = []
        for uid in updated_ids:
            item = await self.get_enriched_by_id(uid)
            if item:
                items.append(item)
        return items

    async def reapprove_all_rejected(self, provider_id: UUID) -> list[VerifyDocumentDomain]:
        stmt = (
            update(self.model)
            .where(self.model.provider_id == provider_id, self.model.is_verify.is_(False))
            .values(is_verify=True)
            .returning(self.model.id)
        )
        res = await self.session.execute(stmt)
        updated_ids = [row[0] for row in res.all()]
        if not updated_ids:
            return []
        items = []
        for uid in updated_ids:
            item = await self.get_enriched_by_id(uid)
            if item:
                items.append(item)
        return items

    async def replace_document_for_provider(
        self,
        provider_id: UUID,
        document_id: UUID,
        document_image: str,
        provider_name: str | None = None,
        provider_email: str | None = None,
    ) -> VerifyDocumentDomain:
        now = datetime.now(timezone.utc)
        # Delete existing verify document for this provider & document type
        del_stmt = delete(self.model).where(
            self.model.provider_id == provider_id,
            self.model.document_id == document_id,
        )
        await self.session.execute(del_stmt)

        new_doc = VerifyDocument(
            id=uuid4(),
            provider_id=provider_id,
            document_id=document_id,
            document_image=document_image,
            provider_name=provider_name,
            provider_email=provider_email,
            is_verify=None,
            created_at=now,
        )
        self.session.add(new_doc)
        await self.session.flush()
        enriched = await self.get_enriched_by_id(new_doc.id)
        return enriched or self.to_domain(new_doc)

    async def get_subcategories_for_document(self, document_id: UUID) -> list[UUID]:
        stmt = select(SubCategoryDocument.sub_category_id).where(
            SubCategoryDocument.document_id == document_id
        )
        res = await self.session.execute(stmt)
        return [row[0] for row in res.all()]
