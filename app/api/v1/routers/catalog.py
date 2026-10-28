from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.catalog import (
    CategoryOut,
    DocumentOut,
    ServiceOut,
    SubCategoryDocumentOut,
    SubCategoryOut,
)
from app.api.v1.schemas.common import Page, PageMeta
from app.core.security.deps import RequireAuth
from app.core.services import catalog_service, service_likes
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/catalog", tags=["Catalog"])


@router.get(
    "/categories",
    response_model=list[CategoryOut],
    operation_id="catalog_list_categories",
    summary="List service categories",
)
async def list_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    active_only: bool = Query(True),
) -> list[CategoryOut]:
    rows = await catalog_service.list_categories(db, active_only=active_only)
    return [CategoryOut.model_validate(r) for r in rows]


@router.get(
    "/sub-categories",
    response_model=list[SubCategoryOut],
    operation_id="catalog_list_sub_categories",
    summary="List sub-categories",
)
async def list_sub_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    category_id: UUID | None = Query(None, alias="categoryId"),
) -> list[SubCategoryOut]:
    rows = await catalog_service.list_sub_categories(db, category_id=category_id)
    return [SubCategoryOut.model_validate(r) for r in rows]


@router.get(
    "/sub-categories/{sub_category_id}/documents",
    response_model=list[SubCategoryDocumentOut],
    operation_id="catalog_list_sub_category_documents",
    summary="Active documents a provider must upload for a sub-category",
)
async def list_sub_category_documents(
    sub_category_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    required_only: bool = Query(True, alias="requiredOnly"),
) -> list[SubCategoryDocumentOut]:
    rows = await catalog_service.list_sub_category_documents(
        db, sub_category_id, required_only=required_only
    )
    return [
        SubCategoryDocumentOut(document=DocumentOut.model_validate(doc), description=desc, is_required=req)
        for doc, desc, req in rows
    ]


@router.get(
    "/documents",
    response_model=list[DocumentOut],
    operation_id="catalog_list_documents",
    summary="Active verification document types",
)
async def list_documents(db: Annotated[AsyncSession, Depends(get_db)]) -> list[DocumentOut]:
    return [DocumentOut.model_validate(d) for d in await catalog_service.list_documents(db)]


@router.get(
    "/services",
    response_model=Page[ServiceOut],
    operation_id="catalog_list_services",
    summary="List approved services",
)
async def list_services(
    db: Annotated[AsyncSession, Depends(get_db)],
    category_id: UUID | None = Query(None, alias="categoryId"),
    provider_id: UUID | None = Query(None, alias="providerId"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[ServiceOut]:
    rows = await catalog_service.list_services(
        db,
        category_id=category_id,
        provider_id=provider_id,
        limit=limit,
        offset=offset,
    )
    return Page(
        items=[ServiceOut.model_validate(r) for r in rows],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.get(
    "/services/{service_id}",
    response_model=ServiceOut,
    operation_id="catalog_get_service",
    summary="Get service by id",
)
async def get_service(
    service_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServiceOut:
    row = await catalog_service.get_service(db, service_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return ServiceOut.model_validate(row)


@router.put(
    "/services/{service_id}/like",
    response_model=ServiceOut,
    operation_id="catalog_like_service",
    summary="Like a service as the authenticated user (list is not taken from the client)",
)
async def like_service(service_id: UUID, ctx: RequireAuth, db: Annotated[AsyncSession, Depends(get_db)]) -> ServiceOut:
    row = await service_likes.set_like(db, service_id, ctx.user_id, liked=True)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return ServiceOut.model_validate(row)


@router.delete(
    "/services/{service_id}/like",
    response_model=ServiceOut,
    operation_id="catalog_unlike_service",
)
async def unlike_service(service_id: UUID, ctx: RequireAuth, db: Annotated[AsyncSession, Depends(get_db)]) -> ServiceOut:
    row = await service_likes.set_like(db, service_id, ctx.user_id, liked=False)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return ServiceOut.model_validate(row)
