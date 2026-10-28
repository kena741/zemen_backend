"""One company row per provider (`companies.provider_id` is unique)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import Company

COMPANY_FIELDS = frozenset(
    {
        "name",
        "website",
        "company_name",
        "industry",
        "company_size",
        "headquarters",
        "founded",
        "profile_bio",
        "banner_image",
    }
)


async def get_for_provider(db: AsyncSession, provider_id: UUID) -> Company | None:
    return (
        await db.execute(select(Company).where(Company.provider_id == provider_id))
    ).scalar_one_or_none()


async def upsert_for_provider(db: AsyncSession, provider_id: UUID, data: dict[str, Any]) -> Company:
    now = datetime.now(UTC)
    patch = {k: v for k, v in data.items() if k in COMPANY_FIELDS}
    name = (patch.get("name") or patch.get("company_name") or "").strip()
    if not name:
        raise ValueError("Company name is required")
    patch["name"] = name
    row = await get_for_provider(db, provider_id)
    if row is None:
        row = Company(id=uuid4(), provider_id=provider_id, created_at=now, **patch)
        db.add(row)
    else:
        for key, value in patch.items():
            setattr(row, key, value)
    row.updated_at = now
    await db.flush()
    await db.refresh(row)
    return row
