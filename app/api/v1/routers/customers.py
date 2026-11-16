"""Customer profile and preferences endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.customer import (
    CheckPhoneRegisteredResponse,
    CustomerCreate,
    CustomerOut,
    CustomerPatch,
)
from app.api.v1.schemas.device import FcmTokenBody
from app.core.security.deps import RequireAuth, RequireCustomer
from app.core.services.customer_profile_service import CustomerProfileService
from app.domain.exceptions import EntityNotFoundError
from app.persistence.repositories.customer_repo import CustomerRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/customers", tags=["Customers"])


def get_customer_profile_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CustomerProfileService:
    return CustomerProfileService(CustomerRepository(db))


@router.get(
    "/me",
    response_model=CustomerOut,
    summary="Get authenticated customer profile",
)
async def get_my_profile(
    ctx: RequireCustomer,
    service: Annotated[CustomerProfileService, Depends(get_customer_profile_service)],
) -> CustomerOut:
    assert ctx.customer_id is not None
    customer = await service.get_profile(ctx.customer_id)
    return CustomerOut.model_validate(customer)


@router.patch(
    "/me",
    response_model=CustomerOut,
    summary="Update authenticated customer profile",
)
async def update_my_profile(
    body: CustomerPatch,
    ctx: RequireCustomer,
    service: Annotated[CustomerProfileService, Depends(get_customer_profile_service)],
) -> CustomerOut:
    assert ctx.customer_id is not None
    updated = await service.update_profile(
        customer_id=ctx.customer_id,
        patch=body.model_dump(exclude_unset=True),
    )
    return CustomerOut.model_validate(updated)


@router.put(
    "/me/fcm-token",
    response_model=CustomerOut,
    summary="Update customer FCM push token",
)
async def update_customer_fcm_token(
    body: FcmTokenBody,
    ctx: RequireCustomer,
    service: Annotated[CustomerProfileService, Depends(get_customer_profile_service)],
) -> CustomerOut:
    assert ctx.customer_id is not None
    await service.update_fcm_token(ctx.customer_id, body.fcm_token)
    customer = await service.get_profile(ctx.customer_id)
    return CustomerOut.model_validate(customer)


@router.delete(
    "/me",
    response_model=CustomerOut,
    summary="Archive authenticated customer profile",
)
async def archive_my_profile(
    ctx: RequireCustomer,
    service: Annotated[CustomerProfileService, Depends(get_customer_profile_service)],
) -> CustomerOut:
    assert ctx.customer_id is not None
    archived = await service.archive_profile(ctx.customer_id)
    return CustomerOut.model_validate(archived)


@router.get(
    "/check-phone",
    response_model=CheckPhoneRegisteredResponse,
    summary="Check if a phone number is registered to any customer",
)
async def check_phone_registered(
    service: Annotated[CustomerProfileService, Depends(get_customer_profile_service)],
    phone: str = Query(..., min_length=4),
) -> CheckPhoneRegisteredResponse:
    is_registered = await service.is_phone_registered(phone)
    return CheckPhoneRegisteredResponse(is_registered=is_registered, phone=phone)


@router.get(
    "/by-email",
    response_model=CustomerOut,
    summary="Lookup customer profile by email",
)
async def get_customer_by_email(
    service: Annotated[CustomerProfileService, Depends(get_customer_profile_service)],
    email: str = Query(..., min_length=3),
) -> CustomerOut:
    customer = await service.get_profile_by_email(email)
    if not customer:
        raise EntityNotFoundError("Customer", email)
    return CustomerOut.model_validate(customer)


@router.get(
    "/by-phone",
    response_model=CustomerOut,
    summary="Lookup customer profile by phone number",
)
async def get_customer_by_phone(
    service: Annotated[CustomerProfileService, Depends(get_customer_profile_service)],
    phone: str = Query(..., min_length=4),
) -> CustomerOut:
    customer = await service.get_profile_by_phone(phone)
    if not customer:
        raise EntityNotFoundError("Customer", phone)
    return CustomerOut.model_validate(customer)


@router.get(
    "/{customer_id}",
    response_model=CustomerOut,
    summary="Get customer profile by ID (for authorized providers / bookings)",
)
async def get_customer_by_id(
    customer_id: UUID,
    ctx: RequireAuth,
    service: Annotated[CustomerProfileService, Depends(get_customer_profile_service)],
) -> CustomerOut:
    customer = await service.get_profile(customer_id)
    return CustomerOut.model_validate(customer)
