"""Public and Mobile Catalog discovery, services search, banners, and coupons router."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.catalog import (
    BannerOut,
    CategoryOut,
    CouponOut,
    DocumentOut,
    ServiceOut,
    SubCategoryDocumentOut,
    SubCategoryOut,
)
from app.api.v1.schemas.common import Page, PageMeta
from app.core.security.deps import RequireAuth
from app.core.services import catalog_service
from app.core.services.catalog_discovery_service import CatalogDiscoveryService
from app.persistence.repositories.banner_repo import BannerRepository
from app.persistence.repositories.category_repo import CategoryRepository
from app.persistence.repositories.coupon_repo import CouponRepository
from app.persistence.repositories.service_repo import ServiceRepository
from app.persistence.repositories.subcategory_repo import SubCategoryRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/catalog", tags=["Catalog"])


def get_catalog_discovery_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CatalogDiscoveryService:
    return CatalogDiscoveryService(
        category_repo=CategoryRepository(db),
        subcategory_repo=SubCategoryRepository(db),
        service_repo=ServiceRepository(db),
        banner_repo=BannerRepository(db),
        coupon_repo=CouponRepository(db),
    )


# ======================== Categories & Subcategories ========================


@router.get(
    "/categories",
    response_model=list[CategoryOut],
    summary="List active service categories",
)
async def list_categories(
    service: Annotated[CatalogDiscoveryService, Depends(get_catalog_discovery_service)],
    active_only: bool = Query(True, alias="activeOnly"),
) -> list[CategoryOut]:
    items = await service.list_categories(active_only=active_only)
    return [CategoryOut.model_validate(c) for c in items]


@router.get(
    "/sub-categories",
    response_model=list[SubCategoryOut],
    summary="List subcategories (optionally filtered by category)",
)
async def list_sub_categories(
    service: Annotated[CatalogDiscoveryService, Depends(get_catalog_discovery_service)],
    category_id: UUID | None = Query(None, alias="categoryId"),
) -> list[SubCategoryOut]:
    items = await service.list_subcategories(category_id=category_id)
    return [SubCategoryOut.model_validate(sc) for sc in items]


@router.get(
    "/sub-categories/{sub_category_id}/documents",
    response_model=list[SubCategoryDocumentOut],
    summary="Active documents required for a sub-category",
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
    summary="Active verification document types",
)
async def list_documents(db: Annotated[AsyncSession, Depends(get_db)]) -> list[DocumentOut]:
    return [DocumentOut.model_validate(d) for d in await catalog_service.list_documents(db)]


# ======================== Services Discovery ========================


@router.get(
    "/services",
    response_model=Page[ServiceOut],
    summary="List approved active public services",
)
async def list_services(
    service: Annotated[CatalogDiscoveryService, Depends(get_catalog_discovery_service)],
    category_id: UUID | None = Query(None, alias="categoryId"),
    sub_category_id: UUID | None = Query(None, alias="subCategoryId"),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[ServiceOut]:
    rows = await service.list_public_services(
        category_id=category_id,
        sub_category_id=sub_category_id,
        search=search,
        offset=offset,
        limit=limit,
    )
    return Page(
        items=[ServiceOut.model_validate(r) for r in rows],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.get(
    "/services/category/{category_id}",
    response_model=Page[ServiceOut],
    summary="Get approved services by category",
)
async def get_services_by_category(
    category_id: UUID,
    service: Annotated[CatalogDiscoveryService, Depends(get_catalog_discovery_service)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[ServiceOut]:
    rows = await service.list_public_services(
        category_id=category_id,
        offset=offset,
        limit=limit,
    )
    return Page(
        items=[ServiceOut.model_validate(r) for r in rows],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.get(
    "/services/nearest",
    response_model=list[ServiceOut],
    summary="Find nearest active services by geolocation",
)
async def list_nearest_services(
    service: Annotated[CatalogDiscoveryService, Depends(get_catalog_discovery_service)],
    lat: float = Query(...),
    lng: float = Query(...),
    radius_km: float = Query(50.0, alias="radiusKm"),
    category_id: UUID | None = Query(None, alias="categoryId"),
) -> list[ServiceOut]:
    rows = await service.list_nearest_services(
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        category_id=category_id,
    )
    return [ServiceOut.model_validate(r) for r in rows]


@router.get(
    "/services/favorites",
    response_model=Page[ServiceOut],
    summary="List customer favourite / liked services",
)
async def list_favourite_services(
    ctx: RequireAuth,
    service: Annotated[CatalogDiscoveryService, Depends(get_catalog_discovery_service)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[ServiceOut]:
    rows = await service.list_favourites(user_id=ctx.user_id, offset=offset, limit=limit)
    return Page(
        items=[ServiceOut.model_validate(r) for r in rows],
        meta=PageMeta(limit=limit, offset=offset),
    )


@router.get(
    "/services/{service_id}",
    response_model=ServiceOut,
    summary="Get service detail by ID",
)
async def get_service_by_id(
    service_id: UUID,
    service: Annotated[CatalogDiscoveryService, Depends(get_catalog_discovery_service)],
) -> ServiceOut:
    item = await service.get_service(service_id)
    return ServiceOut.model_validate(item)


@router.put(
    "/services/{service_id}/like",
    response_model=ServiceOut,
    summary="Toggle / add like to a service",
)
async def like_service(
    service_id: UUID,
    ctx: RequireAuth,
    service: Annotated[CatalogDiscoveryService, Depends(get_catalog_discovery_service)],
) -> ServiceOut:
    item = await service.toggle_like_service(service_id=service_id, user_id=ctx.user_id)
    return ServiceOut.model_validate(item)


@router.delete(
    "/services/{service_id}/like",
    response_model=ServiceOut,
    summary="Unlike a service",
)
async def unlike_service(
    service_id: UUID,
    ctx: RequireAuth,
    service: Annotated[CatalogDiscoveryService, Depends(get_catalog_discovery_service)],
) -> ServiceOut:
    item = await service.toggle_like_service(service_id=service_id, user_id=ctx.user_id)
    return ServiceOut.model_validate(item)


# ======================== Marketing & Promotions ========================


@router.get(
    "/banners",
    response_model=list[BannerOut],
    summary="List active marketing banners",
)
async def list_banners(
    service: Annotated[CatalogDiscoveryService, Depends(get_catalog_discovery_service)],
) -> list[BannerOut]:
    rows = await service.list_banners()
    return [BannerOut.model_validate(r) for r in rows]


@router.get(
    "/coupons",
    response_model=list[CouponOut],
    summary="List available promotional coupons",
)
async def list_coupons(
    service: Annotated[CatalogDiscoveryService, Depends(get_catalog_discovery_service)],
) -> list[CouponOut]:
    rows = await service.list_coupons()
    return [CouponOut.model_validate(r) for r in rows]


@router.get(
    "/coupons/by-code/{code}",
    response_model=CouponOut,
    summary="Lookup coupon by code",
)
async def get_coupon_by_code(
    code: str,
    service: Annotated[CatalogDiscoveryService, Depends(get_catalog_discovery_service)],
) -> CouponOut:
    coupon = await service.get_coupon_by_code(code)
    return CouponOut.model_validate(coupon)
