from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.catalog import (
    SavedServiceDetailOut,
    SavedServicesOut,
    SavedServicesWrite,
)
from app.api.v1.schemas.customer import CustomerCreate, CustomerOut, CustomerPatch
from app.api.v1.schemas.device import FcmTokenBody
from app.core.security.deps import RequireAuth, RequireCustomer
from app.core.services import profile_service, saved_services
from app.core.services.profile_service import ProfileConflict
from app.persistence.sqlalchemy.deps import get_db
from app.persistence.sqlalchemy.models import CustomerServiceDetail

router = APIRouter(prefix="/customers", tags=["Customers"])


def _saved_detail(row: CustomerServiceDetail) -> SavedServiceDetailOut:
    category = {
        "id": row.category_model_id or row.category_id,
        "categoryName": row.category_name,
        "image": row.category_image,
        "active": row.category_active,
    }
    return SavedServiceDetailOut(
        id=row.id,
        service_name=row.service_name,
        description=row.description,
        price=row.price,
        service_image=row.service_images or [],
        category_id=row.category_id,
        sub_category_id=row.sub_category_id,
        category_model=category,
        sub_category_model=row.sub_category_model,
    )


@router.post(
    "/me",
    response_model=CustomerOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="customers_create_me",
    summary="Create the authenticated user's customer profile (wallet starts at 0)",
)
async def customers_create_me(
    body: CustomerCreate,
    ctx: RequireAuth,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CustomerOut:
    try:
        row = await profile_service.create_customer(db, ctx.user_id, body.model_dump(exclude_unset=True))
    except ProfileConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CustomerOut.model_validate(row)


@router.delete(
    "/me",
    response_model=CustomerOut,
    operation_id="customers_archive_me",
    summary="Archive the authenticated customer profile (auth user delete stays on Edge)",
)
async def customers_archive_me(ctx: RequireCustomer, db: Annotated[AsyncSession, Depends(get_db)]) -> CustomerOut:
    assert ctx.customer_id is not None
    row = await profile_service.get_customer_by_id(db, ctx.customer_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return CustomerOut.model_validate(await profile_service.archive_customer(db, row))


@router.get(
    "/me/service-details",
    response_model=SavedServicesOut,
    operation_id="customers_list_service_details",
)
async def customers_list_service_details(
    ctx: RequireCustomer, db: Annotated[AsyncSession, Depends(get_db)]
) -> SavedServicesOut:
    assert ctx.customer_id is not None
    rows = await saved_services.list_for_customer(db, ctx.customer_id)
    return SavedServicesOut(customer_id=ctx.customer_id, service_details_list=[_saved_detail(r) for r in rows])


@router.put(
    "/me/service-details",
    response_model=SavedServicesOut,
    operation_id="customers_replace_service_details",
)
async def customers_replace_service_details(
    body: SavedServicesWrite,
    ctx: RequireCustomer,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SavedServicesOut:
    assert ctx.customer_id is not None
    rows = await saved_services.replace_for_customer(
        db, ctx.customer_id, [i.model_dump(exclude_unset=True) for i in body.service_details_list]
    )
    return SavedServicesOut(customer_id=ctx.customer_id, service_details_list=[_saved_detail(r) for r in rows])


@router.delete(
    "/me/service-details/{detail_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="customers_delete_service_detail",
)
async def customers_delete_service_detail(
    detail_id: UUID,
    ctx: RequireCustomer,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    assert ctx.customer_id is not None
    if not await saved_services.delete_owned_detail(db, ctx.customer_id, detail_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service detail not found")


@router.get(
    "/me",
    response_model=CustomerOut,
    operation_id="customers_me",
    summary="Get authenticated customer profile",
)
async def customers_me(
    ctx: RequireCustomer,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CustomerOut:
    assert ctx.customer_id is not None
    row = await profile_service.get_customer_by_id(db, ctx.customer_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return CustomerOut.model_validate(row)


@router.patch(
    "/me",
    response_model=CustomerOut,
    operation_id="customers_patch_me",
    summary="Update authenticated customer profile (allowlisted fields)",
)
async def customers_patch_me(
    body: CustomerPatch,
    ctx: RequireCustomer,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CustomerOut:
    assert ctx.customer_id is not None
    row = await profile_service.get_customer_by_id(db, ctx.customer_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    updated = await profile_service.update_customer(
        db, row, body.model_dump(exclude_unset=True)
    )
    return CustomerOut.model_validate(updated)


@router.put(
    "/me/fcm-token",
    response_model=CustomerOut,
    operation_id="customers_put_fcm_token",
    summary="Update customer FCM token",
)
async def customers_put_fcm_token(
    body: FcmTokenBody,
    ctx: RequireCustomer,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CustomerOut:
    assert ctx.customer_id is not None
    row = await profile_service.get_customer_by_id(db, ctx.customer_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    updated = await profile_service.update_customer(
        db, row, {"fcm_token": body.fcm_token}
    )
    return CustomerOut.model_validate(updated)
