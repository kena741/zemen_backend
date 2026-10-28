from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.offer import AttachBookingBody, OfferCreate, ServiceOfferOut
from app.core.security.deps import RequireAuth, RequireCustomer
from app.core.services import offer_service
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/offers", tags=["Offers"])


@router.get(
    "",
    response_model=Page[ServiceOfferOut],
    operation_id="offers_list_mine",
    summary="List service offers for customer or provider profile",
)
async def list_mine(
    ctx: RequireAuth,
    db: Annotated[AsyncSession, Depends(get_db)],
    as_role: Literal["customer", "provider"] = Query("customer", alias="as"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[ServiceOfferOut]:
    if as_role == "customer":
        if ctx.customer_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Customer profile required")
        rows = await offer_service.list_offers_for_customer(
            db, ctx.customer_id, limit=limit, offset=offset
        )
    else:
        if ctx.provider_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Provider profile required")
        rows = await offer_service.list_offers_for_provider(
            db, ctx.provider_id, limit=limit, offset=offset
        )
    return Page(
        items=[ServiceOfferOut.model_validate(r) for r in rows],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.post(
    "",
    response_model=ServiceOfferOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="offers_create",
    summary="Customer creates a pending custom-price offer",
)
async def create_offer(
    body: OfferCreate,
    ctx: RequireCustomer,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServiceOfferOut:
    assert ctx.customer_id is not None
    row = await offer_service.create_offer(
        db,
        customer_id=ctx.customer_id,
        user_id=ctx.user_id,
        data=body.model_dump(exclude_unset=True),
    )
    return ServiceOfferOut.model_validate(row)


@router.post(
    "/{offer_id}/accept",
    response_model=ServiceOfferOut,
    operation_id="offers_accept",
    summary="Provider accepts a pending offer",
)
async def accept_offer(
    offer_id: UUID,
    ctx: RequireAuth,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServiceOfferOut:
    if ctx.provider_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Provider profile required")
    row = await offer_service.set_offer_status(
        db,
        offer_id=offer_id,
        new_status="accepted",
        provider_id=ctx.provider_id,
        user_id=ctx.user_id,
    )
    return ServiceOfferOut.model_validate(row)


@router.post(
    "/{offer_id}/reject",
    response_model=ServiceOfferOut,
    operation_id="offers_reject",
    summary="Provider rejects a pending offer",
)
async def reject_offer(
    offer_id: UUID,
    ctx: RequireAuth,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServiceOfferOut:
    if ctx.provider_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Provider profile required")
    row = await offer_service.set_offer_status(
        db,
        offer_id=offer_id,
        new_status="rejected",
        provider_id=ctx.provider_id,
        user_id=ctx.user_id,
    )
    return ServiceOfferOut.model_validate(row)


@router.post(
    "/{offer_id}/cancel",
    response_model=ServiceOfferOut,
    operation_id="offers_cancel",
    summary="Customer cancels a pending offer",
)
async def cancel_offer(
    offer_id: UUID,
    ctx: RequireAuth,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServiceOfferOut:
    if ctx.customer_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Customer profile required")
    row = await offer_service.set_offer_status(
        db,
        offer_id=offer_id,
        new_status="cancelled",
        customer_id=ctx.customer_id,
        user_id=ctx.user_id,
    )
    return ServiceOfferOut.model_validate(row)


@router.post(
    "/{offer_id}/attach-booking",
    response_model=ServiceOfferOut,
    operation_id="offers_attach_booking",
    summary="Customer links an accepted offer to a booking (replaces attach_service_offer_booking RPC)",
)
async def attach_booking(
    offer_id: UUID,
    body: AttachBookingBody,
    ctx: RequireAuth,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServiceOfferOut:
    row = await offer_service.attach_booking(
        db,
        offer_id=offer_id,
        booking_id=body.booking_id,
        customer_id=ctx.customer_id,
        user_id=ctx.user_id,
    )
    return ServiceOfferOut.model_validate(row)
