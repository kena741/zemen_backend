from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import (
    Category,
    Document,
    Service,
    SubCategory,
    SubCategoryDocument,
)


async def list_documents(db: AsyncSession) -> list[Document]:
    stmt = select(Document).where(Document.active.is_(True)).order_by(Document.name)
    return list((await db.execute(stmt)).scalars().all())


async def list_sub_category_documents(
    db: AsyncSession, sub_category_id: UUID, *, required_only: bool = True
) -> list[tuple[Document, str | None, bool]]:
    """Active documents linked to a sub-category. A NULL `isRequired` counts as required."""
    stmt = (
        select(Document, SubCategoryDocument.description, SubCategoryDocument.is_required)
        .join(SubCategoryDocument, SubCategoryDocument.document_id == Document.id)
        .where(SubCategoryDocument.sub_category_id == sub_category_id, Document.active.is_(True))
        .order_by(Document.name, SubCategoryDocument.id)
    )
    if required_only:
        stmt = stmt.where(SubCategoryDocument.is_required.is_not(False))
    seen: dict[UUID, tuple[Document, str | None, bool]] = {}
    for doc, description, is_required in (await db.execute(stmt)).all():
        seen.setdefault(doc.id, (doc, description, is_required is not False))
    return list(seen.values())


async def list_categories(db: AsyncSession, *, active_only: bool = True) -> list[Category]:
    stmt = select(Category).order_by(Category.category_name)
    if active_only:
        stmt = stmt.where(Category.active.is_(True))
    return list((await db.execute(stmt)).scalars().all())


async def list_sub_categories(
    db: AsyncSession, *, category_id: UUID | None = None
) -> list[SubCategory]:
    stmt = select(SubCategory).order_by(SubCategory.sub_category_name)
    if category_id is not None:
        stmt = stmt.where(SubCategory.category_id == category_id)
    return list((await db.execute(stmt)).scalars().all())


async def list_services(
    db: AsyncSession,
    *,
    category_id: UUID | None = None,
    provider_id: UUID | None = None,
    approved_only: bool = True,
    limit: int = 50,
    offset: int = 0,
) -> list[Service]:
    stmt = select(Service).where(Service.is_archived.is_not(True))
    if approved_only:
        stmt = stmt.where(Service.approved.is_(True), Service.status.is_(True))
    if category_id is not None:
        stmt = stmt.where(Service.category_id == category_id)
    if provider_id is not None:
        stmt = stmt.where(Service.provider_id == provider_id)
    stmt = stmt.order_by(Service.created_at.desc()).limit(min(limit, 100)).offset(max(offset, 0))
    return list((await db.execute(stmt)).scalars().all())


async def get_service(db: AsyncSession, service_id: UUID) -> Service | None:
    return (
        await db.execute(select(Service).where(Service.id == service_id))
    ).scalar_one_or_none()
