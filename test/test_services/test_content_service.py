"""Unit tests for ContentAdminService covering Blog, Banners, and Marketing Tracker."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.security.admin_deps import AdminContext
from app.core.services.admin.content_service import ContentAdminService, _slugify
from app.domain.content import (
    BannerDomain,
    BlogCommentDomain,
    BlogPostDomain,
    MarketingColumnDomain,
    MarketingRowDomain,
    MarketingSheetDomain,
)
from app.persistence.sqlalchemy.models.config import Banner
from app.persistence.sqlalchemy.models.content import BlogPost


@pytest.fixture
def mock_admin_ctx() -> AdminContext:
    return AdminContext(
        admin_id=uuid4(),
        user_id=uuid4(),
        email="content_admin@example.com",
        full_name="Marketing Lead",
        role="marketing_lead",
        permissions=["catalog:read", "catalog:write"],
    )


def test_slugify_helper():
    assert _slugify("Hello World!") == "hello-world"
    assert _slugify("  Ethiopian Coffee & Plumbing  ") == "ethiopian-coffee-plumbing"
    assert _slugify("test---slug") == "test-slug"


@pytest.mark.asyncio
async def test_blog_post_create_and_slug_dedup(mock_admin_ctx):
    blog_repo = AsyncMock()
    blog_repo.to_domain = MagicMock()
    comment_repo = AsyncMock()
    banner_repo = AsyncMock()
    tracker_repo = AsyncMock()
    audit_service = AsyncMock()

    # First attempt with an existing slug
    now = datetime.now(timezone.utc)
    post_id = uuid4()
    existing_domain = BlogPostDomain(
        id=uuid4(),
        title="Existing Post",
        slug="plumbing-guide",
        content_html="<p>old</p>",
    )
    blog_repo.get_by_slug.return_value = existing_domain

    created_entity = BlogPost(
        id=post_id,
        title="Plumbing Guide",
        slug="plumbing-guide-abc123",
        content_html="<p>new</p>",
        status="published",
        published_at=now,
    )
    blog_repo.create.return_value = created_entity
    blog_repo.to_domain.return_value = BlogPostDomain(
        id=post_id,
        title="Plumbing Guide",
        slug="plumbing-guide-abc123",
        content_html="<p>new</p>",
        status="published",
        published_at=now,
    )

    service = ContentAdminService(
        blog_repo=blog_repo,
        comment_repo=comment_repo,
        banner_repo=banner_repo,
        tracker_repo=tracker_repo,
        audit_service=audit_service,
    )

    post = await service.create_blog_post(
        title="Plumbing Guide",
        content_html="<p>new</p>",
        post_status="published",
        ctx=mock_admin_ctx,
    )

    assert post.id == post_id
    assert "plumbing-guide" in post.slug
    assert blog_repo.create.called
    create_payload = blog_repo.create.call_args[0][0]
    assert create_payload["slug"].startswith("plumbing-guide-")
    assert audit_service.log_action.called


@pytest.mark.asyncio
async def test_blog_post_get_not_found():
    blog_repo = AsyncMock()
    blog_repo.get_by_id.return_value = None

    service = ContentAdminService(
        blog_repo=blog_repo,
        comment_repo=AsyncMock(),
        banner_repo=AsyncMock(),
        tracker_repo=AsyncMock(),
        audit_service=AsyncMock(),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.get_blog_post(uuid4())
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_blog_comment_moderation(mock_admin_ctx):
    comment_repo = AsyncMock()
    comment_repo.to_domain = MagicMock()
    audit_service = AsyncMock()
    cid = uuid4()
    pid = uuid4()

    comment_domain = BlogCommentDomain(
        id=cid,
        post_id=pid,
        full_name="Selam",
        phone="+251911001122",
        body="Very informative",
        status="approved",
    )
    comment_repo.update_status.return_value = MagicMock()
    comment_repo.to_domain.return_value = comment_domain
    comment_repo.delete_comment.return_value = True

    service = ContentAdminService(
        blog_repo=AsyncMock(),
        comment_repo=comment_repo,
        banner_repo=AsyncMock(),
        tracker_repo=AsyncMock(),
        audit_service=audit_service,
    )

    updated = await service.update_comment_status(cid, "approved", ctx=mock_admin_ctx)
    assert updated.status == "approved"
    assert audit_service.log_action.called

    await service.delete_comment(cid, ctx=mock_admin_ctx)
    assert comment_repo.delete_comment.called


@pytest.mark.asyncio
async def test_banner_crud(mock_admin_ctx):
    banner_repo = AsyncMock()
    banner_repo.to_domain = MagicMock()
    audit_service = AsyncMock()

    banner_entity = Banner(
        id=10,
        banner_name="Summer Special",
        image="https://cdn.example.com/summer.png",
        link="https://zemen.com/summer",
        active=True,
    )
    banner_repo.create.return_value = banner_entity
    banner_repo.to_domain.return_value = BannerDomain(
        id=10,
        banner_name="Summer Special",
        image="https://cdn.example.com/summer.png",
        link="https://zemen.com/summer",
        active=True,
    )
    banner_repo.get_by_id.return_value = banner_entity
    banner_repo.update.return_value = banner_entity

    service = ContentAdminService(
        blog_repo=AsyncMock(),
        comment_repo=AsyncMock(),
        banner_repo=banner_repo,
        tracker_repo=AsyncMock(),
        audit_service=audit_service,
    )

    created = await service.create_banner(
        banner_name="Summer Special",
        image="https://cdn.example.com/summer.png",
        link="https://zemen.com/summer",
        ctx=mock_admin_ctx,
    )
    assert created.id == 10
    assert created.banner_name == "Summer Special"

    updated = await service.update_banner(10, {"active": False}, ctx=mock_admin_ctx)
    assert updated.id == 10

    await service.delete_banner(10, ctx=mock_admin_ctx)
    assert banner_repo.delete.called


@pytest.mark.asyncio
async def test_marketing_tracker_workspace_and_sheets(mock_admin_ctx):
    tracker_repo = AsyncMock()
    audit_service = AsyncMock()

    sheet1 = MarketingSheetDomain(id=uuid4(), name="Sheet 1", position=1)
    sheet2 = MarketingSheetDomain(id=uuid4(), name="Sheet 2", position=2)
    tracker_repo.list_sheets.return_value = [sheet1, sheet2]
    tracker_repo.list_columns.return_value = []
    tracker_repo.list_rows_for_sheet.return_value = []
    tracker_repo.create_sheet.return_value = MarketingSheetDomain(id=uuid4(), name="Sheet 3", position=3)
    tracker_repo.rename_sheet.return_value = MarketingSheetDomain(id=sheet1.id, name="Sheet 1 Renamed", position=1)
    tracker_repo.count_sheets.return_value = 2
    tracker_repo.delete_sheet.return_value = True

    service = ContentAdminService(
        blog_repo=AsyncMock(),
        comment_repo=AsyncMock(),
        banner_repo=AsyncMock(),
        tracker_repo=tracker_repo,
        audit_service=audit_service,
    )

    ws = await service.get_tracker_workspace(requested_sheet_id=sheet2.id)
    assert ws["active_sheet_id"] == sheet2.id
    assert len(ws["sheets"]) == 2

    # Renaming sheet
    renamed = await service.rename_tracker_sheet(sheet1.id, "Sheet 1 Renamed", ctx=mock_admin_ctx)
    assert renamed.name == "Sheet 1 Renamed"

    # Cannot delete last sheet
    tracker_repo.count_sheets.return_value = 1
    with pytest.raises(HTTPException) as exc_info:
        await service.delete_tracker_sheet(sheet1.id, ctx=mock_admin_ctx)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_marketing_tracker_columns_and_rows(mock_admin_ctx):
    tracker_repo = AsyncMock()
    audit_service = AsyncMock()
    col_id = uuid4()
    row_id = uuid4()
    sheet_id = uuid4()

    tracker_repo.add_column.return_value = MarketingColumnDomain(
        id=col_id, key="phone", label="Phone", column_type="text"
    )
    tracker_repo.delete_column.return_value = True
    tracker_repo.add_row.return_value = MarketingRowDomain(
        id=row_id, sheet_id=sheet_id, position=1, values={"phone": "+251911223344"}
    )
    tracker_repo.update_row_values.return_value = MarketingRowDomain(
        id=row_id, sheet_id=sheet_id, position=1, values={"phone": "+251999887766"}
    )
    tracker_repo.delete_row.return_value = True

    service = ContentAdminService(
        blog_repo=AsyncMock(),
        comment_repo=AsyncMock(),
        banner_repo=AsyncMock(),
        tracker_repo=tracker_repo,
        audit_service=audit_service,
    )

    col = await service.add_tracker_column("phone", "Phone", ctx=mock_admin_ctx)
    assert col.key == "phone"

    await service.delete_tracker_column(col_id, ctx=mock_admin_ctx)
    assert tracker_repo.delete_column.called

    row = await service.add_tracker_row(sheet_id, {"phone": "+251911223344"}, ctx=mock_admin_ctx)
    assert row.values["phone"] == "+251911223344"

    patched = await service.patch_tracker_row(row_id, {"phone": "+251999887766"})
    assert patched.values["phone"] == "+251999887766"

    await service.delete_tracker_row(row_id, ctx=mock_admin_ctx)
    assert tracker_repo.delete_row.called
