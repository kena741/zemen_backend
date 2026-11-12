"""Core service for Content, Blog, Banners, and Marketing Tracker."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.core.security.admin_deps import AdminContext
from app.core.services.admin.audit_service import AdminAuditService
from app.domain.content import (
    BannerDomain,
    BlogCommentDomain,
    BlogPostDomain,
    MarketingColumnDomain,
    MarketingRowDomain,
    MarketingSheetDomain,
)
from app.persistence.repositories.banner_repo import BannerRepository
from app.persistence.repositories.blog_comment_repo import BlogCommentRepository
from app.persistence.repositories.blog_post_repo import BlogPostRepository
from app.persistence.repositories.marketing_tracker_repo import MarketingTrackerRepository


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[-\s]+", "-", text).strip("-")


class ContentAdminService:
    def __init__(
        self,
        blog_repo: BlogPostRepository,
        comment_repo: BlogCommentRepository,
        banner_repo: BannerRepository,
        tracker_repo: MarketingTrackerRepository,
        audit_service: AdminAuditService,
    ) -> None:
        self.blog_repo = blog_repo
        self.comment_repo = comment_repo
        self.banner_repo = banner_repo
        self.tracker_repo = tracker_repo
        self.audit_service = audit_service

    # --- Blog Posts ----------------------------------------------------------

    async def list_blog_posts(self) -> list[BlogPostDomain]:
        return await self.blog_repo.list_posts_with_comment_count()

    async def get_blog_post(self, post_id: UUID) -> BlogPostDomain:
        post = await self.blog_repo.get_by_id(post_id)
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog post not found")
        return self.blog_repo.to_domain(post)

    async def create_blog_post(
        self,
        title: str,
        content_html: str,
        slug: str | None = None,
        excerpt: str | None = None,
        cover_image: str | None = None,
        author_name: str | None = None,
        post_status: str = "draft",
        published_at: datetime | None = None,
        ctx: AdminContext | None = None,
    ) -> BlogPostDomain:
        final_slug = slug or _slugify(title)
        existing = await self.blog_repo.get_by_slug(final_slug)
        if existing:
            final_slug = f"{final_slug}-{uuid4().hex[:6]}"

        now = datetime.now(timezone.utc)
        if post_status == "published" and not published_at:
            published_at = now

        created = await self.blog_repo.create({
            "title": title,
            "slug": final_slug,
            "content_html": content_html,
            "excerpt": excerpt,
            "cover_image": cover_image,
            "author_name": author_name,
            "status": post_status,
            "published_at": published_at,
            "created_at": now,
            "updated_at": now,
            "view_count": 0,
            "like_count": 0,
        })
        domain = self.blog_repo.to_domain(created)

        await self.audit_service.log_action(
            action="blog_post.create",
            resource_type="blog_post",
            resource_id=str(domain.id),
            summary=f"Created blog post '{title}' ({domain.slug})",
            metadata={"status": post_status, "slug": final_slug},
            ctx=ctx,
        )
        return domain

    async def update_blog_post(
        self,
        post_id: UUID,
        updates: dict[str, Any],
        ctx: AdminContext | None = None,
    ) -> BlogPostDomain:
        await self.get_blog_post(post_id)
        clean: dict[str, Any] = {}
        for k, v in updates.items():
            if v is not None:
                if k == "status" and v == "published":
                    clean["published_at"] = datetime.now(timezone.utc)
                clean[k] = v

        clean["updated_at"] = datetime.now(timezone.utc)
        updated = await self.blog_repo.update(post_id, clean)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog post not found")

        await self.audit_service.log_action(
            action="blog_post.update",
            resource_type="blog_post",
            resource_id=str(post_id),
            summary=f"Updated blog post {post_id}",
            metadata=clean,
            ctx=ctx,
        )
        entity = await self.blog_repo.get_by_id(post_id)
        return self.blog_repo.to_domain(entity)

    async def delete_blog_post(self, post_id: UUID, ctx: AdminContext | None = None) -> None:
        await self.get_blog_post(post_id)
        await self.blog_repo.delete(post_id)
        await self.audit_service.log_action(
            action="blog_post.delete",
            resource_type="blog_post",
            resource_id=str(post_id),
            summary=f"Deleted blog post {post_id}",
            ctx=ctx,
        )

    # --- Blog Comments -------------------------------------------------------

    async def list_comments_for_post(self, post_id: UUID) -> list[BlogCommentDomain]:
        return await self.comment_repo.list_for_post(post_id)

    async def update_comment_status(
        self,
        comment_id: UUID,
        comment_status: str,
        ctx: AdminContext | None = None,
    ) -> BlogCommentDomain:
        updated = await self.comment_repo.update_status(comment_id, comment_status)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog comment not found")

        await self.audit_service.log_action(
            action="blog_comment.update_status",
            resource_type="blog_comment",
            resource_id=str(comment_id),
            summary=f"Updated comment status to '{comment_status}'",
            ctx=ctx,
        )
        return self.comment_repo.to_domain(updated)

    async def delete_comment(self, comment_id: UUID, ctx: AdminContext | None = None) -> None:
        deleted = await self.comment_repo.delete_comment(comment_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog comment not found")

        await self.audit_service.log_action(
            action="blog_comment.delete",
            resource_type="blog_comment",
            resource_id=str(comment_id),
            summary=f"Deleted comment {comment_id}",
            ctx=ctx,
        )

    # --- Banners -------------------------------------------------------------

    async def list_banners(self) -> list[BannerDomain]:
        return await self.banner_repo.list_all_banners()

    async def create_banner(
        self,
        banner_name: str,
        image: str,
        link: str | None = None,
        active: bool = True,
        ctx: AdminContext | None = None,
    ) -> BannerDomain:
        now = datetime.now(timezone.utc)
        created = await self.banner_repo.create({
            "banner_name": banner_name,
            "image": image,
            "link": link,
            "active": active,
            "created_at": now,
        })
        domain = self.banner_repo.to_domain(created)

        await self.audit_service.log_action(
            action="banner.create",
            resource_type="banner",
            resource_id=str(domain.id),
            summary=f"Created banner '{banner_name}'",
            ctx=ctx,
        )
        return domain

    async def update_banner(
        self,
        banner_id: int,
        updates: dict[str, Any],
        ctx: AdminContext | None = None,
    ) -> BannerDomain:
        clean = {k: v for k, v in updates.items() if v is not None}
        updated = await self.banner_repo.update(banner_id, clean)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner not found")

        await self.audit_service.log_action(
            action="banner.update",
            resource_type="banner",
            resource_id=str(banner_id),
            summary=f"Updated banner {banner_id}",
            metadata=clean,
            ctx=ctx,
        )
        entity = await self.banner_repo.get_by_id(banner_id)
        return self.banner_repo.to_domain(entity)

    async def delete_banner(self, banner_id: int, ctx: AdminContext | None = None) -> None:
        entity = await self.banner_repo.get_by_id(banner_id)
        if not entity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner not found")

        await self.banner_repo.delete(banner_id)
        await self.audit_service.log_action(
            action="banner.delete",
            resource_type="banner",
            resource_id=str(banner_id),
            summary=f"Deleted banner {banner_id}",
            ctx=ctx,
        )

    # --- Marketing Tracker ---------------------------------------------------

    async def get_tracker_workspace(self, requested_sheet_id: UUID | None = None) -> dict[str, Any]:
        sheets = await self.tracker_repo.list_sheets()
        if not sheets:
            # Seed default sheet if empty
            default_sheet = await self.tracker_repo.create_sheet("Leads")
            sheets = [default_sheet]

        active_id = requested_sheet_id
        if not active_id or not any(s.id == active_id for s in sheets):
            active_id = sheets[0].id

        columns = await self.tracker_repo.list_columns()
        rows = await self.tracker_repo.list_rows_for_sheet(active_id)

        return {
            "sheets": sheets,
            "active_sheet_id": active_id,
            "columns": columns,
            "rows": rows,
        }

    async def create_tracker_sheet(
        self, name: str, ctx: AdminContext | None = None
    ) -> MarketingSheetDomain:
        sheet = await self.tracker_repo.create_sheet(name=name)
        await self.audit_service.log_action(
            action="marketing_sheet.create",
            resource_type="marketing_tracker_sheet",
            resource_id=str(sheet.id),
            summary=f"Created marketing tracker sheet '{name}'",
            ctx=ctx,
        )
        return sheet

    async def rename_tracker_sheet(
        self, sheet_id: UUID, new_name: str, ctx: AdminContext | None = None
    ) -> MarketingSheetDomain:
        updated = await self.tracker_repo.rename_sheet(sheet_id=sheet_id, new_name=new_name)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sheet not found")
        await self.audit_service.log_action(
            action="marketing_sheet.rename",
            resource_type="marketing_tracker_sheet",
            resource_id=str(sheet_id),
            summary=f"Renamed sheet {sheet_id} to '{new_name}'",
            ctx=ctx,
        )
        return updated

    async def delete_tracker_sheet(self, sheet_id: UUID, ctx: AdminContext | None = None) -> None:
        total = await self.tracker_repo.count_sheets()
        if total <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the only sheet in marketing tracker",
            )
        deleted = await self.tracker_repo.delete_sheet(sheet_id=sheet_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sheet not found")
        await self.audit_service.log_action(
            action="marketing_sheet.delete",
            resource_type="marketing_tracker_sheet",
            resource_id=str(sheet_id),
            summary=f"Deleted marketing tracker sheet {sheet_id}",
            ctx=ctx,
        )

    async def add_tracker_column(
        self,
        key: str,
        label: str,
        column_type: str = "text",
        ctx: AdminContext | None = None,
    ) -> MarketingColumnDomain:
        col = await self.tracker_repo.add_column(key=key, label=label, column_type=column_type)
        await self.audit_service.log_action(
            action="marketing_column.create",
            resource_type="marketing_tracker_column",
            resource_id=str(col.id),
            summary=f"Added column '{label}' ({key})",
            ctx=ctx,
        )
        return col

    async def delete_tracker_column(self, col_id: UUID, ctx: AdminContext | None = None) -> None:
        deleted = await self.tracker_repo.delete_column(col_id=col_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Column not found")
        await self.audit_service.log_action(
            action="marketing_column.delete",
            resource_type="marketing_tracker_column",
            resource_id=str(col_id),
            summary=f"Deleted column {col_id}",
            ctx=ctx,
        )

    async def add_tracker_row(
        self, sheet_id: UUID, values: dict[str, Any], ctx: AdminContext | None = None
    ) -> MarketingRowDomain:
        row = await self.tracker_repo.add_row(sheet_id=sheet_id, values=values)
        await self.audit_service.log_action(
            action="marketing_row.create",
            resource_type="marketing_tracker_row",
            resource_id=str(row.id),
            summary=f"Added row in sheet {sheet_id}",
            ctx=ctx,
        )
        return row

    async def patch_tracker_row(
        self, row_id: UUID, values: dict[str, Any]
    ) -> MarketingRowDomain:
        updated = await self.tracker_repo.update_row_values(row_id=row_id, values=values)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Row not found")
        return updated

    async def delete_tracker_row(self, row_id: UUID, ctx: AdminContext | None = None) -> None:
        deleted = await self.tracker_repo.delete_row(row_id=row_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Row not found")
        await self.audit_service.log_action(
            action="marketing_row.delete",
            resource_type="marketing_tracker_row",
            resource_id=str(row_id),
            summary=f"Deleted row {row_id}",
            ctx=ctx,
        )

