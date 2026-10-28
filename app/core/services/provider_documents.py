"""Provider-owned verification document rows (`verify_documents`). Storage keys are preserved."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import Document, VerifyDocument


async def list_for_provider(db: AsyncSession, provider_id: UUID) -> list[VerifyDocument]:
    stmt = (
        select(VerifyDocument)
        .where(VerifyDocument.provider_id == provider_id)
        .order_by(VerifyDocument.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def upsert_documents(
    db: AsyncSession,
    *,
    provider_id: UUID,
    provider_name: str | None,
    provider_email: str | None,
    items: list[dict],
) -> list[VerifyDocument]:
    """Insert or replace image for (provider, document). Clients cannot set `isVerify`."""
    now = datetime.now(UTC)
    out: list[VerifyDocument] = []
    for item in items:
        document_id = item.get("document_id")
        image = (item.get("document_image") or "").strip()
        if document_id is None or not image:
            continue
        if (
            await db.execute(select(Document.id).where(Document.id == document_id, Document.active.is_(True)))
        ).scalar_one_or_none() is None:
            continue
        existing = (
            await db.execute(
                select(VerifyDocument)
                .where(
                    VerifyDocument.provider_id == provider_id,
                    VerifyDocument.document_id == document_id,
                )
                .order_by(VerifyDocument.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing is None:
            row = VerifyDocument(
                id=uuid4(),
                created_at=now,
                provider_id=provider_id,
                provider_name=provider_name,
                provider_email=provider_email,
                document_id=document_id,
                document_image=image,
                is_verify=False,
            )
            db.add(row)
            out.append(row)
            continue
        existing.document_image = image
        existing.provider_name = provider_name
        existing.provider_email = provider_email
        if existing.is_verify is not True:
            existing.is_verify = False
        out.append(existing)
    await db.flush()
    return out


async def delete_all_for_provider(db: AsyncSession, provider_id: UUID) -> int:
    rows = (
        await db.execute(select(VerifyDocument).where(VerifyDocument.provider_id == provider_id))
    ).scalars().all()
    for row in rows:
        await db.delete(row)
    await db.flush()
    return len(rows)


async def delete_by_document_id(db: AsyncSession, provider_id: UUID, document_id: UUID) -> int:
    rows = (
        await db.execute(
            select(VerifyDocument).where(
                VerifyDocument.provider_id == provider_id,
                VerifyDocument.document_id == document_id,
            )
        )
    ).scalars().all()
    for row in rows:
        await db.delete(row)
    await db.flush()
    return len(rows)
