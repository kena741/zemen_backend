from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import Service, ServiceOffer


async def list_offers_for_customer(db: AsyncSession, customer_id: UUID, *, limit: int = 50, offset: int = 0):
    stmt = (
        select(ServiceOffer)
        .where(ServiceOffer.customer_id == str(customer_id))
        .order_by(ServiceOffer.created_at.desc())
        .limit(min(limit, 100))
        .offset(max(offset, 0))
    )
    return list((await db.execute(stmt)).scalars().all())


async def list_offers_for_provider(db: AsyncSession, provider_id: UUID, *, limit: int = 50, offset: int = 0):
    stmt = (
        select(ServiceOffer)
        .where(ServiceOffer.provider_id == str(provider_id))
        .order_by(ServiceOffer.created_at.desc())
        .limit(min(limit, 100))
        .offset(max(offset, 0))
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_offer(db: AsyncSession, offer_id: UUID) -> ServiceOffer | None:
    return (
        await db.execute(select(ServiceOffer).where(ServiceOffer.id == offer_id))
    ).scalar_one_or_none()


def _is_customer(offer: ServiceOffer, customer_id: UUID | None, user_id: UUID) -> bool:
    keys = {str(user_id)}
    if customer_id is not None:
        keys.add(str(customer_id))
    return offer.customer_id in keys


def _is_provider(offer: ServiceOffer, provider_id: UUID | None, user_id: UUID) -> bool:
    keys = {str(user_id)}
    if provider_id is not None:
        keys.add(str(provider_id))
    return offer.provider_id in keys


async def create_offer(
    db: AsyncSession, *, customer_id: UUID, user_id: UUID, data: dict[str, Any]
) -> ServiceOffer:
    service_id = str(data["service_id"])
    offered = Decimal(str(data["offered_price"]))
    if offered <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="offeredPrice must be greater than 0")
    try:
        service_uuid = data["service_id"] if isinstance(data["service_id"], UUID) else UUID(service_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid serviceId") from exc
    service = (
        await db.execute(select(Service).where(Service.id == service_uuid))
    ).scalar_one_or_none()
    if service is None or not service.allows_custom_offer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Service does not accept custom prices")
    requested_provider = data.get("provider_id")
    provider_id = str(requested_provider or service.provider_id)
    if provider_id != str(service.provider_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider does not own this service")
    existing = (
        await db.execute(
            select(ServiceOffer.id).where(
                ServiceOffer.customer_id.in_([str(customer_id), str(user_id)]),
                ServiceOffer.service_id == service_id,
                ServiceOffer.status == "pending",
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A pending offer already exists")
    now = datetime.now(UTC)
    row = ServiceOffer(
        id=uuid4(),
        service_id=service_id,
        customer_id=str(customer_id),
        provider_id=provider_id,
        offered_price=offered,
        message=data.get("message"),
        status="pending",
        booking_date=data.get("booking_date"),
        booking_address=data.get("booking_address"),
        service_description=data.get("service_description"),
        expires_at=data.get("expires_at"),
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def set_offer_status(
    db: AsyncSession,
    *,
    offer_id: UUID,
    new_status: str,
    customer_id: UUID | None = None,
    provider_id: UUID | None = None,
    user_id: UUID,
) -> ServiceOffer:
    offer = await get_offer(db, offer_id)
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    if (offer.status or "").lower() != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending offers can change status")
    if new_status == "cancelled":
        if not _is_customer(offer, customer_id, user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    elif new_status in {"accepted", "rejected"}:
        if not _is_provider(offer, provider_id, user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid offer status")
    offer.status = new_status
    offer.updated_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(offer)
    return offer


async def attach_booking(
    db: AsyncSession, *, offer_id: UUID, booking_id: str, customer_id: UUID | None, user_id: UUID
) -> ServiceOffer:
    offer = await get_offer(db, offer_id)
    if offer is None or not _is_customer(offer, customer_id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    if (offer.status or "").lower() != "accepted":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Offer is not accepted")
    current = (offer.booking_id or "").strip()
    if current and current != booking_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Offer already has a booking")
    offer.booking_id = booking_id
    offer.updated_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(offer)
    return offer
