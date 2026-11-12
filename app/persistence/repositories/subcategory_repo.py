"""Repository for SubCategory persistence and document junction mapping."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, select, update

from app.domain.catalog import SubCategoryDomain
from app.persistence.repositories.base import BaseRepository
from app.persistence.sqlalchemy.models.admin import SubCategoryDocument
from app.persistence.sqlalchemy.models.catalog import Category, SubCategory


class SubCategoryRepository(BaseRepository[SubCategory, SubCategoryDomain]):
    model = SubCategory

    def to_domain(
        self,
        entity: SubCategory,
        category_name: str | None = None,
        document_ids: list[UUID] | None = None,
    ) -> SubCategoryDomain:
        return SubCategoryDomain(
            id=entity.id,
            sub_category_name=entity.sub_category_name,
            category_id=entity.category_id,
            category_name=category_name,
            is_free=entity.is_free,
            document_ids=document_ids or [],
        )

    async def list_all(self) -> list[SubCategoryDomain]:
        stmt = (
            select(self.model, Category.category_name.label("category_name"))
            .outerjoin(Category, self.model.category_id == Category.id)
            .order_by(self.model.sub_category_name.asc())
        )
        res = await self.session.execute(stmt)
        subcats = res.all()

        # Query all document mappings
        doc_res = await self.session.execute(select(SubCategoryDocument))
        doc_map: dict[UUID, list[UUID]] = {}
        for d in doc_res.scalars().all():
            doc_map.setdefault(d.sub_category_id, []).append(d.document_id)

        return [
            self.to_domain(sc, category_name=c_name, document_ids=doc_map.get(sc.id, []))
            for sc, c_name in subcats
        ]

    async def get_by_id_enriched(self, subcat_id: UUID) -> SubCategoryDomain | None:
        stmt = (
            select(self.model, Category.category_name.label("category_name"))
            .outerjoin(Category, self.model.category_id == Category.id)
            .where(self.model.id == subcat_id)
        )
        res = await self.session.execute(stmt)
        row = res.first()
        if not row:
            return None
        sc, c_name = row

        doc_stmt = select(SubCategoryDocument.document_id).where(
            SubCategoryDocument.sub_category_id == subcat_id
        )
        doc_res = await self.session.execute(doc_stmt)
        doc_ids = [r[0] for r in doc_res.all()]
        return self.to_domain(sc, category_name=c_name, document_ids=doc_ids)

    async def create_subcategory(
        self,
        sub_category_name: str,
        category_id: UUID,
        is_free: bool = False,
        document_ids: list[UUID] | None = None,
    ) -> SubCategoryDomain:
        subcat_id = uuid4()
        entity = SubCategory(
            id=subcat_id,
            sub_category_name=sub_category_name.strip(),
            category_id=category_id,
            is_free=is_free,
        )
        self.session.add(entity)
        await self.session.flush()

        if document_ids:
            for doc_id in document_ids:
                junc = SubCategoryDocument(
                    id=uuid4(),
                    sub_category_id=subcat_id,
                    document_id=doc_id,
                    is_required=True,
                )
                self.session.add(junc)
            await self.session.flush()

        return await self.get_by_id_enriched(subcat_id) or self.to_domain(entity, document_ids=document_ids)

    async def update_subcategory(
        self,
        subcat_id: UUID,
        sub_category_name: str | None = None,
        category_id: UUID | None = None,
        is_free: bool | None = None,
        document_ids: list[UUID] | None = None,
    ) -> SubCategoryDomain | None:
        values: dict[str, Any] = {}
        if sub_category_name is not None:
            values["sub_category_name"] = sub_category_name.strip()
        if category_id is not None:
            values["category_id"] = category_id
        if is_free is not None:
            values["is_free"] = is_free

        if values:
            stmt = update(self.model).where(self.model.id == subcat_id).values(**values)
            await self.session.execute(stmt)

        # Replace junction rows if document_ids was provided
        if document_ids is not None:
            del_stmt = delete(SubCategoryDocument).where(SubCategoryDocument.sub_category_id == subcat_id)
            await self.session.execute(del_stmt)
            for doc_id in document_ids:
                junc = SubCategoryDocument(
                    id=uuid4(),
                    sub_category_id=subcat_id,
                    document_id=doc_id,
                    is_required=True,
                )
                self.session.add(junc)
            await self.session.flush()

        return await self.get_by_id_enriched(subcat_id)

    async def get_document_map(self) -> dict[str, list[str]]:
        res = await self.session.execute(select(SubCategoryDocument))
        mapping: dict[str, list[str]] = {}
        for d in res.scalars().all():
            mapping.setdefault(str(d.sub_category_id), []).append(str(d.document_id))
        return mapping
