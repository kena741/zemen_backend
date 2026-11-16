"""Router for Custom Service Offers negotiation and booking creation."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.booking import BookingOut
from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.offer import AttachBookingBody, OfferCreate, ServiceOfferOut
from app.core.security.deps import RequireAuth, RequireCustomer, RequireProvider
from app.core.services.service_offer_service import ServiceOfferService
from app.persistence.repositories.mobile_booking_repo import MobileBookingRepository
from app.persistence.repositories.service_offer_repo import ServiceOfferRepository
from app.persistence.repositories.service_repo import ServiceRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/offers", tags=["Offers"])


def get_service_offer_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServiceOfferService:
    return ServiceOfferService(
        offer_repo=ServiceOfferRepository(db),
        service_repo=ServiceRepository(db),
        booking_repo=MobileBookingRepository(db),
    )


@router.get(
    "",
    response_model=Page[ServiceOfferOut],
    summary="List service offers for customer or provider profile",
)
async def list_mine(
    ctx: RequireAuth,
    service: Annotated[ServiceOfferService, Depends(get_service_offer_service)],
    as_role: Literal["customer", "provider"] = Query("customer", alias="as"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[ServiceOfferOut]:
    if as_role == "customer":
        assert ctx.customer_id is not None
        rows = await service.list_customer_offers(ctx.customer_id, limit=limit, offset=offset)
    else:
        assert ctx.provider_id is not None
        rows = await service.list_provider_offers(ctx.provider_id, limit=limit, offset=offset)
    return Page(
        items=[ServiceOfferOut.model_validate(r) for r in rows],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.post(
    "",
    response_model=ServiceOfferOut,
    status_code=status.HTTP_201_CREATED,
    summary="Customer creates a pending custom-price offer",
)
async def create_offer(
    body: OfferCreate,
    ctx: RequireCustomer,
    service: Annotated[ServiceOfferService, Depends(get_service_offer_service)],
) -> ServiceOfferOut:
    assert ctx.customer_id is not None
    created = await service.create_offer(
        customer_id=ctx.customer_id,
        payload=body.model_dump(exclude_unset=True),
    )
    return ServiceOfferOut.model_validate(created)


@router.get(
    "/by-booking/{booking_id}",
    response_model=ServiceOfferOut,
    summary="Get service offer linked to a booking ID",
)
async def get_by_booking_id(
    booking_id: str,
    service: Annotated[ServiceOfferService, Depends(get_service_offer_service)],
) -> ServiceOfferOut:
    item = await service.get_by_booking_id(booking_id)
    return ServiceOfferOut.model_validate(item)


@router.get(
    "/{offer_id}",
    response_model=ServiceOfferOut,
    summary="Get single service offer detail",
)
async def get_offer(
    offer_id: UUID,
    ctx: RequireAuth,
    service: Annotated[ServiceOfferService, Depends(get_service_offer_service)],
) -> ServiceOfferOut:
    actor_id = ctx.customer_id or ctx.provider_id or ctx.user_id
    actor_role = "customer" if ctx.customer_id else "provider"
    item = await service.get_offer(offer_id=offer_id, actor_id=actor_id, actor_role=actor_role)
    return ServiceOfferOut.model_validate(item)


@router.post(
    "/{offer_id}/accept",
    response_model=ServiceOfferOut,
    summary="Provider accepts a pending offer, creates booking, and links booking ID",
)
async def accept_offer(
    offer_id: UUID,
    ctx: RequireProvider,
    service: Annotated[ServiceOfferService, Depends(get_service_offer_service)],
) -> ServiceOfferOut:
    assert ctx.provider_id is not None
    await service.accept_and_book(offer_id=offer_id, provider_id=ctx.provider_id)
    updated_offer = await service.get_offer(
        offer_id=offer_id, actor_id=ctx.provider_id, actor_role="provider"
    )
    return ServiceOfferOut.model_validate(updated_offer)


@router.post(
    "/{offer_id}/create-booking",
    response_model=BookingOut,
    summary="Create booking from an accepted offer",
)
async def create_booking_from_offer(
    offer_id: UUID,
    ctx: RequireProvider,
    service: Annotated[ServiceOfferService, Depends(get_service_offer_service)],
) -> BookingOut:
    assert ctx.provider_id is not None
    booking = await service.accept_and_book(offer_id=offer_id, provider_id=ctx.provider_id)
    return BookingOut.model_validate(booking)


@router.post(
    "/{offer_id}/reject",
    response_model=ServiceOfferOut,
    summary="Provider rejects a pending offer",
)
async def reject_offer(
    offer_id: UUID,
    ctx: RequireProvider,
    service: Annotated[ServiceOfferService, Depends(get_service_offer_service)],
) -> ServiceOfferOut:
    assert ctx.provider_id is not None
    updated = await service.reject_offer(offer_id=offer_id, provider_id=ctx.provider_id)
    return ServiceOfferOut.model_validate(updated)


@router.post(
    "/{offer_id}/cancel",
    response_model=ServiceOfferOut,
    summary="Customer cancels a pending offer",
)
async def cancel_offer(
    offer_id: UUID,
    ctx: RequireCustomer,
    service: Annotated[ServiceOfferService, Depends(get_service_offer_service)],
) -> ServiceOfferOut:
    assert ctx.customer_id is not None
    updated = await service.cancel_offer(offer_id=offer_id, customer_id=ctx.customer_id)
    return ServiceOfferOut.model_validate(updated)


@router.post(
    "/{offer_id}/attach-booking",
    response_model=ServiceOfferOut,
    summary="Link an accepted offer to a booking (replaces RPC attach_service_offer_booking)",
)
async def attach_booking(
    offer_id: UUID,
    body: AttachBookingBody,
    ctx: RequireAuth,
    service: Annotated[ServiceOfferService, Depends(get_service_offer_service)],
) -> ServiceOfferOut:
    actor_id = ctx.customer_id or ctx.provider_id or ctx.user_id
    updated = await service.attach_booking(
        offer_id=offer_id, booking_id=body.booking_id, actor_id=actor_id
    )
    return ServiceOfferOut.model_validate(updated)
