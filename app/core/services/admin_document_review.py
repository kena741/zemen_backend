"""Provider document verification (verify_documents → provider.verified_subcategory_ids).

Ports `verifyDocumentsSlice.ts` from lolelink-admin. A sub-category stays in
`verified_subcategory_ids` while at least one of its linked documents is
approved for that provider.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.admin_deps import AdminContext
from app.core.services.admin_audit import log_admin_activity
from app.persistence.sqlalchemy.models import (
    Document,
    Provider,
    SubCategory,
    SubCategoryDocument,
    VerifyDocument,
)

DocumentStatus = Literal["pending", "verified", "rejected"]


def status_of(is_verify: bool | None) -> DocumentStatus:
    if is_verify is True:
        return "verified"
    if is_verify is False:
        return "rejected"
    return "pending"


async def list_documents(
    db: AsyncSession,
    *,
    provider_id: UUID | None,
    status: DocumentStatus | None,
    limit: int,
    offset: int,
) -> list[dict]:
    stmt = select(VerifyDocument)
    if provider_id is not None:
        stmt = stmt.where(VerifyDocument.provider_id == provider_id)
    if status == "verified":
        stmt = stmt.where(VerifyDocument.is_verify.is_(True))
    elif status == "rejected":
        stmt = stmt.where(VerifyDocument.is_verify.is_(False))
    elif status == "pending":
        stmt = stmt.where(VerifyDocument.is_verify.is_(None))
    stmt = stmt.order_by(VerifyDocument.created_at.desc()).limit(limit).offset(offset)
    rows = list((await db.execute(stmt)).scalars().all())

    doc_ids = {r.document_id for r in rows if r.document_id}
    doc_names: dict[UUID, str | None] = {}
    sub_names: dict[UUID, str] = {}
    if doc_ids:
        for d in (await db.execute(select(Document).where(Document.id.in_(doc_ids)))).scalars():
            doc_names[d.id] = d.name
        links = (
            await db.execute(
                select(SubCategoryDocument.document_id, SubCategory.sub_category_name)
                .join(SubCategory, SubCategory.id == SubCategoryDocument.sub_category_id)
                .where(SubCategoryDocument.document_id.in_(doc_ids))
            )
        ).all()
        for document_id, name in links:
            sub_names[document_id] = name

    return [
        {
            "row": r,
            "document_name": doc_names.get(r.document_id) if r.document_id else None,
            "sub_category_name": sub_names.get(r.document_id) if r.document_id else None,
        }
        for r in rows
    ]


async def _subcategory_ids_for_documents(db: AsyncSession, document_ids: set[UUID]) -> set[UUID]:
    if not document_ids:
        return set()
    return set(
        (
            await db.execute(
                select(SubCategoryDocument.sub_category_id).where(
                    SubCategoryDocument.document_id.in_(document_ids)
                )
            )
        ).scalars()
    )


async def _lock_provider(db: AsyncSession, provider_id: UUID) -> Provider:
    provider = (
        await db.execute(select(Provider).where(Provider.id == provider_id).with_for_update())
    ).scalar_one_or_none()
    if provider is None:
        raise LookupError("Provider not found")
    return provider


async def _add_verified_subcategories(
    db: AsyncSession, provider_id: UUID, document_ids: set[UUID]
) -> None:
    sub_ids = await _subcategory_ids_for_documents(db, document_ids)
    if not sub_ids:
        return
    provider = await _lock_provider(db, provider_id)
    existing = list(provider.verified_subcategory_ids or [])
    have = set(existing)
    merged = existing + sorted(s for s in sub_ids if s not in have)
    if merged != existing:
        provider.verified_subcategory_ids = merged
        await db.flush()


async def _drop_orphaned_subcategories(
    db: AsyncSession, provider_id: UUID, document_id: UUID
) -> None:
    sub_ids = await _subcategory_ids_for_documents(db, {document_id})
    if not sub_ids:
        return
    provider = await _lock_provider(db, provider_id)

    links = (
        await db.execute(
            select(SubCategoryDocument.sub_category_id, SubCategoryDocument.document_id).where(
                SubCategoryDocument.sub_category_id.in_(sub_ids)
            )
        )
    ).all()
    approved_doc_ids = set(
        (
            await db.execute(
                select(VerifyDocument.document_id).where(
                    VerifyDocument.provider_id == provider_id,
                    VerifyDocument.is_verify.is_(True),
                )
            )
        ).scalars()
    )
    still_backed = {sub for sub, doc in links if doc in approved_doc_ids}
    remove = sub_ids - still_backed
    if not remove:
        return
    current = list(provider.verified_subcategory_ids or [])
    nxt = [s for s in current if s not in remove]
    if nxt != current:
        provider.verified_subcategory_ids = nxt
        await db.flush()


async def get_document(db: AsyncSession, document_row_id: UUID) -> VerifyDocument | None:
    return (
        await db.execute(
            select(VerifyDocument).where(VerifyDocument.id == document_row_id).with_for_update()
        )
    ).scalar_one_or_none()


async def verify_document(db: AsyncSession, ctx: AdminContext, row: VerifyDocument) -> VerifyDocument:
    before = row.is_verify
    row.is_verify = True
    await db.flush()
    if row.document_id:
        await _add_verified_subcategories(db, row.provider_id, {row.document_id})
    await log_admin_activity(
        db,
        ctx,
        action="verify",
        resource_type="document",
        resource_id=row.id,
        summary=f"Verified provider document {row.id}",
        metadata={
            "changes": {"isVerify": {"from": before, "to": True}},
            "provider_id": str(row.provider_id),
        },
    )
    await db.refresh(row)
    return row


async def reject_document(
    db: AsyncSession, ctx: AdminContext, row: VerifyDocument, reason: str
) -> VerifyDocument:
    before = row.is_verify
    was_approved = before is True
    row.is_verify = False
    await db.flush()
    if was_approved and row.document_id:
        await _drop_orphaned_subcategories(db, row.provider_id, row.document_id)
    await log_admin_activity(
        db,
        ctx,
        action="reject",
        resource_type="document",
        resource_id=row.id,
        summary=(
            f"Revoked approval for provider document {row.id}"
            if was_approved
            else f"Rejected provider document {row.id}"
        ),
        metadata={
            "changes": {"isVerify": {"from": before, "to": False}},
            "provider_id": str(row.provider_id),
            "revoked_approval": was_approved,
            "rejection_reason": reason,
        },
    )
    await db.refresh(row)
    return row


async def bulk_verify(
    db: AsyncSession,
    ctx: AdminContext,
    provider_id: UUID,
    *,
    from_status: DocumentStatus,
) -> list[VerifyDocument]:
    """Approve every pending (or every rejected) document for one provider."""
    cond = (
        VerifyDocument.is_verify.is_(None)
        if from_status == "pending"
        else VerifyDocument.is_verify.is_(False)
    )
    rows = list(
        (
            await db.execute(
                select(VerifyDocument)
                .where(VerifyDocument.provider_id == provider_id, cond)
                .with_for_update()
            )
        ).scalars()
    )
    for r in rows:
        r.is_verify = True
    await db.flush()
    await _add_verified_subcategories(db, provider_id, {r.document_id for r in rows if r.document_id})
    if rows:
        await log_admin_activity(
            db,
            ctx,
            action="verify",
            resource_type="document",
            resource_id=provider_id,
            summary=(
                f"Approved all pending documents for provider {provider_id}"
                if from_status == "pending"
                else f"Re-approved rejected documents for provider {provider_id}"
            ),
            metadata={"count": len(rows), "document_row_ids": [str(r.id) for r in rows]},
        )
    return rows
