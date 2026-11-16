"""Service for managing provider handymen personnel and assignments."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.phone import normalize_ethiopian_phone
from app.domain.exceptions import EntityNotFoundError
from app.domain.provider import HandymanDomain
from app.persistence.repositories.handyman_repo import HandymanRepository
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
        "category_id",
        "sub_category_id",
        "slug",
    }
)


class HandymanService:
    """Class-based service coordinating handyman personnel operations."""

    def __init__(self, handyman_repo: HandymanRepository) -> None:
        self.handyman_repo = handyman_repo

    async def list_for_provider(self, provider_id: UUID) -> list[HandymanDomain]:
        return await self.handyman_repo.list_by_provider(provider_id)

    async def get_handyman(self, handyman_id: UUID, provider_id: UUID | None = None) -> HandymanDomain:
        handyman = await self.handyman_repo.get_by_id(handyman_id)
        if not handyman or (provider_id and handyman.provider_id != provider_id):
            raise EntityNotFoundError("Handyman", handyman_id)
        return handyman

    async def create_handyman(self, provider_id: UUID, data: dict[str, Any]) -> HandymanDomain:
        phone = data.get("phone_number")
        if phone:
            phone = normalize_ethiopian_phone(phone)

        domain = HandymanDomain(
            id=uuid4(),
            provider_id=provider_id,
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            user_name=data.get("user_name"),
            email=data.get("email"),
            phone_number=phone,
            profile_image=data.get("profile_image"),
            active=data.get("active", True),
            address=data.get("address"),
            category_id=data.get("category_id"),
            sub_category_id=data.get("sub_category_id"),
            created_at=datetime.now(timezone.utc),
        )
        return await self.handyman_repo.create_handyman(domain)

    async def update_handyman(
        self, handyman_id: UUID, provider_id: UUID, patch: dict[str, Any]
    ) -> HandymanDomain:
        cleaned = {k: v for k, v in patch.items() if k in HANDYMAN_PATCH_FIELDS and v is not None}
        updated = await self.handyman_repo.update_handyman(handyman_id, provider_id, cleaned)
        if not updated:
            raise EntityNotFoundError("Handyman", handyman_id)
        return updated

    async def delete_handyman(self, handyman_id: UUID, provider_id: UUID) -> bool:
        deleted = await self.handyman_repo.delete_handyman(handyman_id, provider_id)
        if not deleted:
            raise EntityNotFoundError("Handyman", handyman_id)
        return True


# Backward compatibility helpers for existing prototype tests
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
        created_at=datetime.now(timezone.utc),
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
