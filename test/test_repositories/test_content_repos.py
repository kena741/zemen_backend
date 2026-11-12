"""Unit and mapping tests for Content, Blog, Banner, and Marketing Tracker repositories."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.persistence.repositories.banner_repo import BannerRepository
from app.persistence.repositories.blog_comment_repo import BlogCommentRepository
from app.persistence.repositories.blog_post_repo import BlogPostRepository
from app.persistence.repositories.marketing_tracker_repo import MarketingTrackerRepository
from app.persistence.sqlalchemy.models.config import Banner
from app.persistence.sqlalchemy.models.content import (
    BlogComment,
    BlogPost,
    MarketingTrackerColumn,
    MarketingTrackerRow,
    MarketingTrackerSheet,
)
from .conftest import RepoMockSession


@pytest.mark.asyncio
async def test_blog_post_repo_to_domain():
    post_id = uuid4()
    now = datetime.now(timezone.utc)
    entity = BlogPost(
        id=post_id,
        title="Modern Plumbing Tips",
        slug="modern-plumbing-tips",
        content_html="<p>Always inspect seals.</p>",
        excerpt="Tips for homeowners",
        cover_image="https://example.com/cover.jpg",
        author_name="Admin",
        status="published",
        published_at=now,
        view_count=42,
        like_count=10,
        created_at=now,
        updated_at=now,
    )

    session = RepoMockSession(scalar_one_or_none_value=entity)
    repo = BlogPostRepository(session)  # type: ignore[arg-type]
    domain = repo.to_domain(entity, comment_count=3)

    assert domain.id == post_id
    assert domain.slug == "modern-plumbing-tips"
    assert domain.comment_count == 3
    assert domain.view_count == 42
    assert domain.like_count == 10


@pytest.mark.asyncio
async def test_blog_post_repo_get_by_slug():
    post_id = uuid4()
    entity = BlogPost(
        id=post_id,
        title="Test Post",
        slug="test-post",
        content_html="<p>Test</p>",
        status="draft",
        view_count=0,
        like_count=0,
    )
    session = RepoMockSession(scalar_one_or_none_value=entity)
    repo = BlogPostRepository(session)  # type: ignore[arg-type]

    res = await repo.get_by_slug("test-post")
    assert res is not None
    assert res.title == "Test Post"
    assert len(session.executed_statements) == 1


@pytest.mark.asyncio
async def test_blog_comment_repo_lifecycle():
    cid = uuid4()
    pid = uuid4()
    comment = BlogComment(
        id=cid,
        post_id=pid,
        full_name="Abebe Bikila",
        phone="+251911223344",
        body="Great post!",
        status="approved",
    )
    session = RepoMockSession(scalar_one_or_none_value=comment, scalars_value=[comment])
    repo = BlogCommentRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(comment)
    assert domain.id == cid
    assert domain.full_name == "Abebe Bikila"

    comments = await repo.list_for_post(pid)
    assert len(comments) == 1
    assert comments[0].body == "Great post!"

    upd = await repo.update_status(cid, "hidden")
    assert upd is not None

    deleted = await repo.delete_comment(cid)
    assert deleted is True


@pytest.mark.asyncio
async def test_banner_repo_lifecycle():
    banner = Banner(
        id=1,
        banner_name="Holiday Promo",
        image="https://example.com/banner.png",
        link="https://example.com/promo",
        active=True,
    )
    session = RepoMockSession(scalars_value=[banner])
    repo = BannerRepository(session)  # type: ignore[arg-type]

    domain = repo.to_domain(banner)
    assert domain.id == 1
    assert domain.banner_name == "Holiday Promo"

    banners = await repo.list_all_banners()
    assert len(banners) == 1
    assert banners[0].banner_name == "Holiday Promo"


@pytest.mark.asyncio
async def test_marketing_tracker_repo_sheets():
    sheet_id = uuid4()
    sheet = MarketingTrackerSheet(
        id=sheet_id,
        name="Campaign Q1",
        position=1,
        created_at=datetime.now(timezone.utc),
    )
    session = RepoMockSession(scalar_one_or_none_value=sheet, scalars_value=[sheet])
    repo = MarketingTrackerRepository(session)

    sheets = await repo.list_sheets()
    assert len(sheets) == 1
    assert sheets[0].name == "Campaign Q1"

    created = await repo.create_sheet("Campaign Q2")
    assert created.name == "Campaign Q2"
    assert len(session.added_items) == 1

    renamed = await repo.rename_sheet(sheet_id, "Campaign Q1 Renamed")
    assert renamed is not None
    assert renamed.name == "Campaign Q1"

    deleted = await repo.delete_sheet(sheet_id)
    assert deleted is True


@pytest.mark.asyncio
async def test_marketing_tracker_repo_columns_and_rows():
    col_id = uuid4()
    col = MarketingTrackerColumn(
        id=col_id,
        key="lead_name",
        label="Lead Name",
        column_type="text",
        position=1,
        is_system=False,
    )
    row_id = uuid4()
    sheet_id = uuid4()
    row = MarketingTrackerRow(
        id=row_id,
        sheet_id=sheet_id,
        position=1,
        values={"lead_name": "Acme Corp"},
    )
    session = RepoMockSession(scalar_one_or_none_value=col, scalars_value=[col])
    repo = MarketingTrackerRepository(session)

    columns = await repo.list_columns()
    assert len(columns) == 1
    assert columns[0].key == "lead_name"

    # Row operations
    session.scalars_list = [row]
    session.scalar_value = row
    rows = await repo.list_rows_for_sheet(sheet_id)
    assert len(rows) == 1
    assert rows[0].values["lead_name"] == "Acme Corp"

    patched = await repo.update_row_values(row_id, {"lead_name": "Global Acme Corp"})
    assert patched is not None

    del_row = await repo.delete_row(row_id)
    assert del_row is True
