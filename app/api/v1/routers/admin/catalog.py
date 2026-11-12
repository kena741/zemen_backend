"""Admin Catalog (Category, SubCategory) and Service Review API router."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.admin.requests.catalog import (
    ApproveByProviderRequest,
    CreateCategoryRequest,
    CreateSubCategoryRequest,
    FeatureDecisionRequest,
    SoftArchiveServiceRequest,
    UpdateCategoryRequest,
    UpdateSubCategoryRequest,
)
from app.api.v1.schemas.admin.responses.catalog import (
    CategoryItemResponse,
    CategoryListResponse,
    CategorySingleResponse,
    ServiceItemResponse,
    ServiceListResponse,
    ServiceSingleResponse,
    SubCategoryItemResponse,
    SubCategoryListResponse,
    SubCategorySingleResponse,
)
from app.core.security.admin_deps import AdminContext, require_admin_permission
from app.core.services.admin.audit_service import AdminAuditService
from app.core.services.admin.catalog_service import CatalogAdminService
from app.persistence.repositories.activity_log_repo import ActivityLogRepository
from app.persistence.repositories.category_repo import CategoryRepository
from app.persistence.repositories.service_repo import ServiceRepository
from app.persistence.repositories.subcategory_repo import SubCategoryRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/admin", tags=["admin-catalog"])

Db = Annotated[AsyncSession, Depends(get_db)]
CanReadCatalog = Annotated[AdminContext, Depends(require_admin_permission("catalog:read"))]
CanWriteCatalog = Annotated[AdminContext, Depends(require_admin_permission("catalog:write"))]
CanReadServices = Annotated[AdminContext, Depends(require_admin_permission("services:read"))]
CanWriteServices = Annotated[AdminContext, Depends(require_admin_permission("services:write"))]


def _get_catalog_service(db: AsyncSession) -> CatalogAdminService:
    audit_repo = ActivityLogRepository(db)
    audit_service = AdminAuditService(audit_repo)
    cat_repo = CategoryRepository(db)
    subcat_repo = SubCategoryRepository(db)
    srv_repo = ServiceRepository(db)
    return CatalogAdminService(
        category_repo=cat_repo,
        subcategory_repo=subcat_repo,
        service_repo=srv_repo,
        audit_service=audit_service,
    )


# ---------------- Categories ----------------
@router.get(
    "/categories",
    response_model=CategoryListResponse,
    operation_id="admin_categories_list",
    summary="List all categories",
)
async def list_categories(_: CanReadCatalog, db: Db) -> CategoryListResponse:
    service = _get_catalog_service(db)
    cats = await service.list_categories()
    return CategoryListResponse(data=[CategoryItemResponse.model_validate(c) for c in cats])


@router.post(
    "/categories",
    response_model=CategorySingleResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_categories_create",
    summary="Create category",
)
async def create_category(
    body: CreateCategoryRequest,
    ctx: CanWriteCatalog,
    db: Db,
) -> CategorySingleResponse:
    service = _get_catalog_service(db)
    domain = await service.create_category(
        category_name=body.category_name,
        image=body.image,
        active=body.active,
        description=body.description,
        ctx=ctx,
    )
    return CategorySingleResponse(data=CategoryItemResponse.model_validate(domain))


@router.put(
    "/categories/{category_id}",
    response_model=CategorySingleResponse,
    operation_id="admin_categories_update",
    summary="Update category",
)
async def update_category(
    category_id: UUID,
    body: UpdateCategoryRequest,
    ctx: CanWriteCatalog,
    db: Db,
) -> CategorySingleResponse:
    service = _get_catalog_service(db)
    domain = await service.update_category(
        category_id=category_id,
        category_name=body.category_name,
        image=body.image,
        active=body.active,
        description=body.description,
        ctx=ctx,
    )
    return CategorySingleResponse(data=CategoryItemResponse.model_validate(domain))


@router.delete(
    "/categories/{category_id}",
    status_code=status.HTTP_200_OK,
    operation_id="admin_categories_delete",
    summary="Delete category",
)
async def delete_category(
    category_id: UUID,
    ctx: CanWriteCatalog,
    db: Db,
) -> dict[str, bool]:
    service = _get_catalog_service(db)
    await service.delete_category(category_id, ctx=ctx)
    return {"ok": True}


# ---------------- Subcategories ----------------
@router.get(
    "/subcategories",
    response_model=SubCategoryListResponse,
    operation_id="admin_subcategories_list",
    summary="List all subcategories",
)
async def list_subcategories(_: CanReadCatalog, db: Db) -> SubCategoryListResponse:
    service = _get_catalog_service(db)
    subcats = await service.list_subcategories()
    return SubCategoryListResponse(data=[SubCategoryItemResponse.model_validate(s) for s in subcats])


@router.get(
    "/subcategories/document-map",
    response_model=dict[str, list[str]],
    operation_id="admin_subcategories_document_map",
    summary="Get subcategory to document ID mapping",
)
async def get_subcategory_document_map(_: CanReadCatalog, db: Db) -> dict[str, list[str]]:
    service = _get_catalog_service(db)
    return await service.get_document_map()


@router.post(
    "/subcategories",
    response_model=SubCategorySingleResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_subcategories_create",
    summary="Create subcategory with document requirements",
)
async def create_subcategory(
    body: CreateSubCategoryRequest,
    ctx: CanWriteCatalog,
    db: Db,
) -> SubCategorySingleResponse:
    service = _get_catalog_service(db)
    domain = await service.create_subcategory(
        sub_category_name=body.sub_category_name,
        category_id=body.category_id,
        is_free=body.is_free,
        document_ids=body.document_ids,
        ctx=ctx,
    )
    return SubCategorySingleResponse(data=SubCategoryItemResponse.model_validate(domain))


@router.put(
    "/subcategories/{subcategory_id}",
    response_model=SubCategorySingleResponse,
    operation_id="admin_subcategories_update",
    summary="Update subcategory",
)
async def update_subcategory(
    subcategory_id: UUID,
    body: UpdateSubCategoryRequest,
    ctx: CanWriteCatalog,
    db: Db,
) -> SubCategorySingleResponse:
    service = _get_catalog_service(db)
    domain = await service.update_subcategory(
        subcat_id=subcategory_id,
        sub_category_name=body.sub_category_name,
        category_id=body.category_id,
        is_free=body.is_free,
        document_ids=body.document_ids,
        ctx=ctx,
    )
    return SubCategorySingleResponse(data=SubCategoryItemResponse.model_validate(domain))


@router.delete(
    "/subcategories/{subcategory_id}",
    status_code=status.HTTP_200_OK,
    operation_id="admin_subcategories_delete",
    summary="Delete subcategory",
)
async def delete_subcategory(
    subcategory_id: UUID,
    ctx: CanWriteCatalog,
    db: Db,
) -> dict[str, bool]:
    service = _get_catalog_service(db)
    await service.delete_subcategory(subcategory_id, ctx=ctx)
    return {"ok": True}


# ---------------- Services Review ----------------
@router.get(
    "/services",
    response_model=ServiceListResponse,
    operation_id="admin_services_list",
    summary="List services for review",
)
async def list_services(
    _: CanReadServices,
    db: Db,
    include_archived: bool = Query(default=False, alias="includeArchived"),
    provider_id: UUID | None = Query(default=None, alias="providerId"),
) -> ServiceListResponse:
    service = _get_catalog_service(db)
    services = await service.list_services(
        include_archived=include_archived,
        provider_id=provider_id,
    )
    return ServiceListResponse(data=[ServiceItemResponse.model_validate(s) for s in services])


@router.post(
    "/services/{service_id}/approve",
    operation_id="admin_services_approve_by_id",
    summary="Approve service by ID",
)
async def approve_service_by_id(
    service_id: UUID,
    ctx: CanWriteServices,
    db: Db,
) -> dict[str, int]:
    service = _get_catalog_service(db)
    await service.approve_by_id(service_id, ctx=ctx)
    return {"count": 1}


@router.post(
    "/services/approve-by-provider",
    operation_id="admin_services_approve_by_provider",
    summary="Approve all unapproved services for provider",
)
async def approve_services_by_provider(
    body: ApproveByProviderRequest,
    ctx: CanWriteServices,
    db: Db,
) -> dict[str, int]:
    service = _get_catalog_service(db)
    count = await service.approve_by_provider(body.provider_id, ctx=ctx)
    return {"count": count}


@router.post(
    "/services/{service_id}/featured",
    operation_id="admin_services_decide_featured",
    summary="Decide featured status for service",
)
async def decide_featured_status(
    service_id: UUID,
    body: FeatureDecisionRequest,
    ctx: CanWriteServices,
    db: Db,
) -> dict[str, int]:
    service = _get_catalog_service(db)
    await service.decide_feature_request(service_id, body.decision, ctx=ctx)
    return {"count": 1}


@router.patch(
    "/services/{service_id}/archive",
    operation_id="admin_services_archive",
    summary="Soft archive or unarchive service",
)
async def archive_service(
    service_id: UUID,
    body: SoftArchiveServiceRequest,
    ctx: CanWriteServices,
    db: Db,
) -> dict[str, str]:
    service = _get_catalog_service(db)
    await service.soft_archive_service(service_id, body.action, ctx=ctx)
    return {"id": str(service_id)}


@router.get(
    "/services/badge-count",
    operation_id="admin_services_badge_count",
    summary="Get unapproved and featured pending service count",
)
async def get_services_badge_count(
    _: CanReadServices,
    db: Db,
) -> dict[str, int]:
    service = _get_catalog_service(db)
    count = await service.count_services_badge()
    return {"count": count}

