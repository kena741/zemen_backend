"""Admin Content, Blog, Banners, and Marketing Tracker API router."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.admin.requests.content import (
    AddTrackerColumnRequest,
    AddTrackerRowRequest,
    CreateBannerRequest,
    CreateBlogPostRequest,
    CreateTrackerSheetRequest,
    DeleteBlogCommentRequest,
    PatchTrackerRowRequest,
    RenameTrackerSheetRequest,
    UpdateBannerRequest,
    UpdateBlogCommentRequest,
    UpdateBlogPostRequest,
)
from app.api.v1.schemas.admin.responses.content import (
    BannerListResponse,
    BannerResponseItem,
    BannerSingleResponse,
    BlogCommentListResponse,
    BlogCommentResponseItem,
    BlogPostListResponse,
    BlogPostResponseItem,
    BlogPostSingleResponse,
    MarketingColumnResponseItem,
    MarketingRowResponseItem,
    MarketingSheetResponseItem,
    MarketingTrackerWorkspaceResponse,
)
from app.core.security.admin_deps import AdminContext, require_admin_permission
from app.core.services.admin.audit_service import AdminAuditService
from app.core.services.admin.content_service import ContentAdminService
from app.persistence.repositories.activity_log_repo import ActivityLogRepository
from app.persistence.repositories.banner_repo import BannerRepository
from app.persistence.repositories.blog_comment_repo import BlogCommentRepository
from app.persistence.repositories.blog_post_repo import BlogPostRepository
from app.persistence.repositories.marketing_tracker_repo import MarketingTrackerRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/admin", tags=["admin-content"])

Db = Annotated[AsyncSession, Depends(get_db)]
CanReadCatalog = Annotated[AdminContext, Depends(require_admin_permission("catalog:read"))]
CanWriteCatalog = Annotated[AdminContext, Depends(require_admin_permission("catalog:write"))]


def _get_content_service(db: AsyncSession) -> ContentAdminService:
    blog_repo = BlogPostRepository(db)
    comment_repo = BlogCommentRepository(db)
    banner_repo = BannerRepository(db)
    tracker_repo = MarketingTrackerRepository(db)
    audit_repo = ActivityLogRepository(db)
    audit_service = AdminAuditService(audit_repo)

    return ContentAdminService(
        blog_repo=blog_repo,
        comment_repo=comment_repo,
        banner_repo=banner_repo,
        tracker_repo=tracker_repo,
        audit_service=audit_service,
    )


# --- Blog Posts --------------------------------------------------------------


@router.get(
    "/blog-posts",
    response_model=BlogPostListResponse,
    operation_id="admin_blog_list_posts",
    summary="List all blog posts with comment counts",
)
@router.get("/content/blog-posts", response_model=BlogPostListResponse, include_in_schema=False)
async def list_blog_posts(_: CanReadCatalog, db: Db) -> BlogPostListResponse:
    service = _get_content_service(db)
    posts = await service.list_blog_posts()
    return BlogPostListResponse(data=[BlogPostResponseItem.model_validate(p) for p in posts])


@router.post(
    "/blog-posts",
    response_model=BlogPostSingleResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_blog_create_post",
    summary="Create a new blog post",
)
async def create_blog_post(
    body: CreateBlogPostRequest,
    ctx: CanWriteCatalog,
    db: Db,
) -> BlogPostSingleResponse:
    service = _get_content_service(db)
    created = await service.create_blog_post(
        title=body.title,
        content_html=body.content_html,
        slug=body.slug,
        excerpt=body.excerpt,
        cover_image=body.cover_image,
        author_name=body.author_name,
        post_status=body.status,
        published_at=body.published_at,
        ctx=ctx,
    )
    return BlogPostSingleResponse(data=BlogPostResponseItem.model_validate(created))


@router.patch(
    "/blog-posts/{post_id}",
    response_model=BlogPostSingleResponse,
    operation_id="admin_blog_update_post_path",
    summary="Update blog post by path ID",
)
async def update_blog_post_path(
    post_id: UUID,
    body: UpdateBlogPostRequest,
    ctx: CanWriteCatalog,
    db: Db,
) -> BlogPostSingleResponse:
    service = _get_content_service(db)
    updated = await service.update_blog_post(
        post_id=post_id,
        updates=body.model_dump(exclude_unset=True, exclude={"id"}),
        ctx=ctx,
    )
    return BlogPostSingleResponse(data=BlogPostResponseItem.model_validate(updated))


@router.patch(
    "/blog-posts",
    response_model=BlogPostSingleResponse,
    operation_id="admin_blog_update_post_body",
    summary="Update blog post by body ID",
)
async def update_blog_post_body(
    body: UpdateBlogPostRequest,
    ctx: CanWriteCatalog,
    db: Db,
) -> BlogPostSingleResponse:
    if not body.id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="id is required in body")
    service = _get_content_service(db)
    updated = await service.update_blog_post(
        post_id=body.id,
        updates=body.model_dump(exclude_unset=True, exclude={"id"}),
        ctx=ctx,
    )
    return BlogPostSingleResponse(data=BlogPostResponseItem.model_validate(updated))


@router.delete(
    "/blog-posts/{post_id}",
    status_code=status.HTTP_200_OK,
    operation_id="admin_blog_delete_post_path",
    summary="Delete blog post by path ID",
)
async def delete_blog_post_path(
    post_id: UUID,
    ctx: CanWriteCatalog,
    db: Db,
) -> dict[str, bool]:
    service = _get_content_service(db)
    await service.delete_blog_post(post_id=post_id, ctx=ctx)
    return {"ok": True}


# --- Blog Comments -----------------------------------------------------------


@router.get(
    "/blog-posts/{post_id}/comments",
    response_model=BlogCommentListResponse,
    operation_id="admin_blog_list_comments",
    summary="List comments for a specific blog post",
)
async def list_blog_comments(
    post_id: UUID,
    _: CanReadCatalog,
    db: Db,
) -> BlogCommentListResponse:
    service = _get_content_service(db)
    comments = await service.list_comments_for_post(post_id=post_id)
    return BlogCommentListResponse(
        data=[BlogCommentResponseItem.model_validate(c) for c in comments]
    )


@router.patch(
    "/blog-posts/{post_id}/comments",
    response_model=BlogCommentResponseItem,
    operation_id="admin_blog_update_comment_status",
    summary="Update status of a blog comment",
)
async def update_blog_comment(
    post_id: UUID,
    body: UpdateBlogCommentRequest,
    ctx: CanWriteCatalog,
    db: Db,
) -> BlogCommentResponseItem:
    service = _get_content_service(db)
    updated = await service.update_comment_status(
        comment_id=body.comment_id,
        comment_status=body.status,
        ctx=ctx,
    )
    return BlogCommentResponseItem.model_validate(updated)


@router.delete(
    "/blog-posts/{post_id}/comments",
    status_code=status.HTTP_200_OK,
    operation_id="admin_blog_delete_comment",
    summary="Delete a blog comment",
)
async def delete_blog_comment(
    post_id: UUID,
    body: DeleteBlogCommentRequest,
    ctx: CanWriteCatalog,
    db: Db,
) -> dict[str, bool]:
    service = _get_content_service(db)
    await service.delete_comment(comment_id=body.comment_id, ctx=ctx)
    return {"ok": True}


# --- Banners -----------------------------------------------------------------


@router.get(
    "/banners",
    response_model=BannerListResponse,
    operation_id="admin_banners_list",
    summary="List all promotional banners",
)
async def list_banners(_: CanReadCatalog, db: Db) -> BannerListResponse:
    service = _get_content_service(db)
    banners = await service.list_banners()
    return BannerListResponse(data=[BannerResponseItem.model_validate(b) for b in banners])


@router.post(
    "/banners",
    response_model=BannerSingleResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_banners_create",
    summary="Create a new promotional banner",
)
async def create_banner(
    body: CreateBannerRequest,
    ctx: CanWriteCatalog,
    db: Db,
) -> BannerSingleResponse:
    service = _get_content_service(db)
    created = await service.create_banner(
        banner_name=body.banner_name,
        image=body.image,
        link=body.link,
        active=body.active,
        ctx=ctx,
    )
    return BannerSingleResponse(data=BannerResponseItem.model_validate(created))


@router.patch(
    "/banners/{banner_id}",
    response_model=BannerSingleResponse,
    operation_id="admin_banners_update_path",
    summary="Update banner by path ID",
)
async def update_banner_path(
    banner_id: int,
    body: UpdateBannerRequest,
    ctx: CanWriteCatalog,
    db: Db,
) -> BannerSingleResponse:
    service = _get_content_service(db)
    updated = await service.update_banner(
        banner_id=banner_id,
        updates=body.model_dump(exclude_unset=True, exclude={"id"}),
        ctx=ctx,
    )
    return BannerSingleResponse(data=BannerResponseItem.model_validate(updated))


@router.patch(
    "/banners",
    response_model=BannerSingleResponse,
    operation_id="admin_banners_update_body",
    summary="Update banner by body ID",
)
async def update_banner_body(
    body: UpdateBannerRequest,
    ctx: CanWriteCatalog,
    db: Db,
) -> BannerSingleResponse:
    if not body.id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="id is required in body")
    service = _get_content_service(db)
    updated = await service.update_banner(
        banner_id=body.id,
        updates=body.model_dump(exclude_unset=True, exclude={"id"}),
        ctx=ctx,
    )
    return BannerSingleResponse(data=BannerResponseItem.model_validate(updated))


@router.delete(
    "/banners/{banner_id}",
    status_code=status.HTTP_200_OK,
    operation_id="admin_banners_delete_path",
    summary="Delete banner by path ID",
)
async def delete_banner_path(
    banner_id: int,
    ctx: CanWriteCatalog,
    db: Db,
) -> dict[str, bool]:
    service = _get_content_service(db)
    await service.delete_banner(banner_id=banner_id, ctx=ctx)
    return {"ok": True}


# --- Marketing Tracker (Spreadsheet CRM) -------------------------------------


@router.get(
    "/marketing-tracker",
    response_model=MarketingTrackerWorkspaceResponse,
    operation_id="admin_marketing_tracker_workspace",
    summary="Load marketing tracker spreadsheet workspace",
)
async def get_marketing_tracker(
    _: CanReadCatalog,
    db: Db,
    sheet_id: UUID | None = Query(default=None, alias="sheet_id"),
) -> MarketingTrackerWorkspaceResponse:
    service = _get_content_service(db)
    ws = await service.get_tracker_workspace(requested_sheet_id=sheet_id)
    return MarketingTrackerWorkspaceResponse.model_validate(ws)


@router.post(
    "/marketing-tracker/sheets",
    response_model=MarketingSheetResponseItem,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_marketing_tracker_create_sheet",
    summary="Create a new sheet tab in marketing tracker",
)
async def create_tracker_sheet(
    body: CreateTrackerSheetRequest,
    ctx: CanWriteCatalog,
    db: Db,
) -> MarketingSheetResponseItem:
    service = _get_content_service(db)
    sheet = await service.create_tracker_sheet(name=body.name, ctx=ctx)
    return MarketingSheetResponseItem.model_validate(sheet)


@router.patch(
    "/marketing-tracker/sheets/{sheet_id}",
    response_model=MarketingSheetResponseItem,
    operation_id="admin_marketing_tracker_rename_sheet",
    summary="Rename marketing tracker sheet",
)
async def rename_tracker_sheet(
    sheet_id: UUID,
    body: RenameTrackerSheetRequest,
    ctx: CanWriteCatalog,
    db: Db,
) -> MarketingSheetResponseItem:
    service = _get_content_service(db)
    sheet = await service.rename_tracker_sheet(sheet_id=sheet_id, new_name=body.name, ctx=ctx)
    return MarketingSheetResponseItem.model_validate(sheet)


@router.delete(
    "/marketing-tracker/sheets/{sheet_id}",
    status_code=status.HTTP_200_OK,
    operation_id="admin_marketing_tracker_delete_sheet",
    summary="Delete sheet from marketing tracker",
)
async def delete_tracker_sheet(
    sheet_id: UUID,
    ctx: CanWriteCatalog,
    db: Db,
) -> dict[str, bool]:
    service = _get_content_service(db)
    await service.delete_tracker_sheet(sheet_id=sheet_id, ctx=ctx)
    return {"ok": True}


@router.post(
    "/marketing-tracker/columns",
    response_model=MarketingColumnResponseItem,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_marketing_tracker_add_column",
    summary="Add a new column definition to marketing tracker",
)
async def add_tracker_column(
    body: AddTrackerColumnRequest,
    ctx: CanWriteCatalog,
    db: Db,
) -> MarketingColumnResponseItem:
    service = _get_content_service(db)
    col = await service.add_tracker_column(
        key=body.key,
        label=body.label,
        column_type=body.column_type,
        ctx=ctx,
    )
    return MarketingColumnResponseItem.model_validate(col)


@router.delete(
    "/marketing-tracker/columns/{column_id}",
    status_code=status.HTTP_200_OK,
    operation_id="admin_marketing_tracker_delete_column",
    summary="Delete a column definition from marketing tracker",
)
async def delete_tracker_column(
    column_id: UUID,
    ctx: CanWriteCatalog,
    db: Db,
) -> dict[str, bool]:
    service = _get_content_service(db)
    await service.delete_tracker_column(col_id=column_id, ctx=ctx)
    return {"ok": True}


@router.post(
    "/marketing-tracker/rows",
    response_model=MarketingRowResponseItem,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_marketing_tracker_add_row",
    summary="Add a new lead row to marketing tracker",
)
async def add_tracker_row(
    body: AddTrackerRowRequest,
    ctx: CanWriteCatalog,
    db: Db,
) -> MarketingRowResponseItem:
    service = _get_content_service(db)
    row = await service.add_tracker_row(
        sheet_id=body.sheet_id,
        values=body.values,
        ctx=ctx,
    )
    return MarketingRowResponseItem.model_validate(row)


@router.patch(
    "/marketing-tracker/rows/{row_id}",
    response_model=MarketingRowResponseItem,
    operation_id="admin_marketing_tracker_patch_row",
    summary="Update cell values in marketing tracker row",
)
async def patch_tracker_row(
    row_id: UUID,
    body: PatchTrackerRowRequest,
    _: CanWriteCatalog,
    db: Db,
) -> MarketingRowResponseItem:
    service = _get_content_service(db)
    row = await service.patch_tracker_row(row_id=row_id, values=body.values)
    return MarketingRowResponseItem.model_validate(row)


@router.delete(
    "/marketing-tracker/rows/{row_id}",
    status_code=status.HTTP_200_OK,
    operation_id="admin_marketing_tracker_delete_row",
    summary="Delete a row from marketing tracker",
)
async def delete_tracker_row(
    row_id: UUID,
    ctx: CanWriteCatalog,
    db: Db,
) -> dict[str, bool]:
    service = _get_content_service(db)
    await service.delete_tracker_row(row_id=row_id, ctx=ctx)
    return {"ok": True}
