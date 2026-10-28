from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import Handyman

HANDYMAN_PATCH_FIELDS = frozenset(
    {
        "first_name",
        "last_name",
        "user_name",
        "email",
        "phone_number",
        "profile_image",
        "active",
        "is_active",
        "address",
        "slug",
    }
)


async def list_for_provider(db: AsyncSession, provider_id: UUID) -> list[Handyman]:
    stmt = (
        select(Handyman)
        .where(Handyman.provider_id == provider_id)
        .order_by(Handyman.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_owned_handyman(
    db: AsyncSession, provider_id: UUID, handyman_id: UUID
) -> Handyman | None:
    return (
        await db.execute(
            select(Handyman).where(
                Handyman.id == handyman_id,
                Handyman.provider_id == provider_id,
            )
        )
    ).scalar_one_or_none()


async def create_handyman(
    db: AsyncSession, *, provider_id: UUID, data: dict[str, Any]
) -> Handyman:
    row = Handyman(
        id=uuid4(),
        provider_id=provider_id,
        first_name=data.get("first_name"),
        last_name=data.get("last_name"),
        user_name=data.get("user_name"),
        email=data.get("email"),
        phone_number=data.get("phone_number"),
        profile_image=data.get("profile_image"),
        address=data.get("address"),
        active=data.get("active", True),
        is_active=data.get("is_active", True),
        slug=data.get("slug"),
        created_at=datetime.now(UTC),
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def update_handyman(
    db: AsyncSession, handyman: Handyman, patch: dict[str, Any]
) -> Handyman:
    cleaned = {k: v for k, v in patch.items() if k in HANDYMAN_PATCH_FIELDS and v is not None}
    for key, value in cleaned.items():
        setattr(handyman, key, value)
    await db.flush()
    await db.refresh(handyman)
    return handyman


async def delete_handyman(db: AsyncSession, handyman: Handyman) -> None:
    await db.delete(handyman)
    await db.flush()
