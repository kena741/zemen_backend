from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import Customer, Provider


class ProfileConflict(Exception):
    pass

# Fields clients may change via PATCH — never wallet / activation / admin flags.
CUSTOMER_PATCH_FIELDS = frozenset(
    {
        "first_name",
        "last_name",
        "user_name",
        "email",
        "country_code",
        "phone",
        "profile_pic",
        "fcm_token",
        "customer_addresses",
        "default_address",
        "slug",
    }
)

PROVIDER_PATCH_FIELDS = frozenset(
    {
        "first_name",
        "last_name",
        "user_name",
        "phone_number",
        "email",
        "profile_image",
        "banner",
        "address",
        "country",
        "country_code",
        "currency",
        "location",
        "social_links",
        "fcm_token",
        "slug",
    }
)


async def get_customer_by_user_id(db: AsyncSession, user_id: UUID) -> Customer | None:
    return (
        await db.execute(
            select(Customer).where(
                Customer.user_id == user_id,
                Customer.archived_at.is_(None),
            )
        )
    ).scalar_one_or_none()


async def get_customer_by_id(db: AsyncSession, customer_id: UUID) -> Customer | None:
    return (
        await db.execute(
            select(Customer).where(
                Customer.id == customer_id,
                Customer.archived_at.is_(None),
            )
        )
    ).scalar_one_or_none()


async def get_provider_by_user_id(db: AsyncSession, user_id: UUID) -> Provider | None:
    return (
        await db.execute(
            select(Provider).where(
                Provider.user_id == user_id,
                Provider.archived_at.is_(None),
            )
        )
    ).scalar_one_or_none()


async def get_provider_by_id(db: AsyncSession, provider_id: UUID) -> Provider | None:
    return (
        await db.execute(
            select(Provider).where(
                Provider.id == provider_id,
                Provider.archived_at.is_(None),
            )
        )
    ).scalar_one_or_none()


def filter_customer_patch(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if k in CUSTOMER_PATCH_FIELDS and v is not None}


def filter_provider_patch(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if k in PROVIDER_PATCH_FIELDS and v is not None}


async def update_customer(
    db: AsyncSession, customer: Customer, patch: dict[str, Any]
) -> Customer:
    for key, value in filter_customer_patch(patch).items():
        setattr(customer, key, value)
    customer.updated_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(customer)
    return customer


async def update_provider(
    db: AsyncSession, provider: Provider, patch: dict[str, Any]
) -> Provider:
    for key, value in filter_provider_patch(patch).items():
        setattr(provider, key, value)
    provider.updated_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(provider)
    return provider


async def _existing_customer(db: AsyncSession, user_id: UUID) -> Customer | None:
    return (
        await db.execute(select(Customer).where(Customer.user_id == user_id))
    ).scalar_one_or_none()


async def _existing_provider(db: AsyncSession, user_id: UUID) -> Provider | None:
    return (
        await db.execute(select(Provider).where(Provider.user_id == user_id))
    ).scalar_one_or_none()


async def create_customer(db: AsyncSession, user_id: UUID, data: dict[str, Any]) -> Customer:
    """Create (or restore) the caller's customer row. Wallet is always 0."""
    now = datetime.now(UTC)
    existing = await _existing_customer(db, user_id)
    if existing is not None and existing.archived_at is None:
        raise ProfileConflict("Customer profile already exists")
    fields = filter_customer_patch(data)
    first = (fields.get("first_name") or "").strip()
    last = (fields.get("last_name") or "").strip()
    phone = (fields.get("phone") or "").strip()
    if not first or not last or not phone:
        raise ValueError("first_name, last_name and phone are required")
    try:
        if existing is not None:
            for key, value in fields.items():
                setattr(existing, key, value)
            existing.archived_at = None
            existing.active = True
            existing.updated_at = now
            await db.flush()
            await db.refresh(existing)
            return existing
        row = Customer(
            id=user_id,
            user_id=user_id,
            first_name=first,
            last_name=last,
            phone=phone,
            email=fields.get("email"),
            country_code=fields.get("country_code"),
            user_name=fields.get("user_name"),
            profile_pic=fields.get("profile_pic"),
            fcm_token=fields.get("fcm_token"),
            slug=fields.get("slug"),
            customer_addresses=fields.get("customer_addresses"),
            default_address=fields.get("default_address"),
            wallet_amount=0,
            active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        await db.flush()
        await db.refresh(row)
        return row
    except IntegrityError as exc:
        raise ProfileConflict("Phone or email is already registered") from exc


async def create_provider(
    db: AsyncSession,
    user_id: UUID,
    data: dict[str, Any],
    *,
    provider_type: Literal["individual", "company"] | None = None,
) -> Provider:
    now = datetime.now(UTC)
    existing = await _existing_provider(db, user_id)
    if existing is not None and existing.archived_at is None:
        raise ProfileConflict("Provider profile already exists")
    fields = filter_provider_patch(data)
    try:
        if existing is not None:
            for key, value in fields.items():
                setattr(existing, key, value)
            existing.archived_at = None
            existing.active = True
            existing.updated_at = now
            await db.flush()
            await db.refresh(existing)
            return existing
        row = Provider(
            id=user_id,
            user_id=user_id,
            first_name=fields.get("first_name"),
            last_name=fields.get("last_name"),
            user_name=fields.get("user_name"),
            phone_number=fields.get("phone_number"),
            email=fields.get("email"),
            profile_image=fields.get("profile_image"),
            banner=fields.get("banner"),
            address=fields.get("address"),
            country=fields.get("country"),
            country_code=fields.get("country_code"),
            currency=fields.get("currency"),
            location=fields.get("location"),
            slug=fields.get("slug"),
            social_links=fields.get("social_links") or [],
            fcm_token=fields.get("fcm_token"),
            user_type="Provider",
            provider_type=provider_type,
            wallet_amount="0",
            active=True,
            activation_paid=False,
            service_tier_max=0,
            verified_subcategory_ids=[],
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        await db.flush()
        await db.refresh(row)
        return row
    except IntegrityError as exc:
        raise ProfileConflict("User name or account is already registered") from exc


async def archive_customer(db: AsyncSession, customer: Customer) -> Customer:
    customer.archived_at = datetime.now(UTC)
    customer.active = False
    customer.updated_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(customer)
    return customer


async def archive_provider(db: AsyncSession, provider: Provider) -> Provider:
    provider.archived_at = datetime.now(UTC)
    provider.active = False
    provider.updated_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(provider)
    return provider
