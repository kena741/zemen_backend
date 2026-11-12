"""Integration tests for Admin Content, Blog, Banners, and Marketing Tracker API endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.security.admin_deps import AdminContext
from app.domain.content import (
    BannerDomain,
    BlogCommentDomain,
    BlogPostDomain,
    MarketingColumnDomain,
    MarketingRowDomain,
    MarketingSheetDomain,
)
from .conftest import ApiTestDbSession


@pytest.fixture
def content_admin_context() -> AdminContext:
    return AdminContext(
        admin_id=uuid4(),
        user_id=uuid4(),
        email="content_admin@lolelink.com",
        full_name="Content Lead",
        role="content_manager",
        permissions=["catalog:read", "catalog:write"],
    )


def test_list_blog_posts_api(api_client, content_admin_context):
    post_id = uuid4()
    mock_post = BlogPostDomain(
        id=post_id,
        title="Top 5 Maintenance Tips",
        slug="top-5-maintenance-tips",
        content_html="<p>Tips content</p>",
        comment_count=4,
        status="published",
    )

    with patch("app.api.v1.routers.admin.content._get_content_service") as mock_svc_getter:
        mock_svc = mock_svc_getter.return_value
        mock_svc.list_blog_posts = AsyncMock(return_value=[mock_post])

        db = ApiTestDbSession()
        client = api_client(admin_context=content_admin_context, db_session=db)
        res = client.get("/api/v1/admin/blog-posts")

        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == str(post_id)
        assert data[0]["commentCount"] == 4
        assert data[0]["contentHtml"] == "<p>Tips content</p>"


def test_create_blog_post_api(api_client, content_admin_context):
    post_id = uuid4()
    mock_post = BlogPostDomain(
        id=post_id,
        title="New Feature Announcement",
        slug="new-feature-announcement",
        content_html="<p>Exciting news</p>",
        status="published",
    )

    with patch("app.api.v1.routers.admin.content._get_content_service") as mock_svc_getter:
        mock_svc = mock_svc_getter.return_value
        mock_svc.create_blog_post = AsyncMock(return_value=mock_post)

        db = ApiTestDbSession()
        client = api_client(admin_context=content_admin_context, db_session=db)
        payload = {
            "title": "New Feature Announcement",
            "contentHtml": "<p>Exciting news</p>",
            "status": "published",
        }
        res = client.post("/api/v1/admin/blog-posts", json=payload)

        assert res.status_code == 201
        data = res.json()["data"]
        assert data["id"] == str(post_id)
        assert data["title"] == "New Feature Announcement"


def test_blog_comments_api(api_client, content_admin_context):
    post_id = uuid4()
    comment_id = uuid4()
    mock_comment = BlogCommentDomain(
        id=comment_id,
        post_id=post_id,
        full_name="Almaz",
        phone="+251911443322",
        body="Very helpful, thank you!",
        status="approved",
    )

    with patch("app.api.v1.routers.admin.content._get_content_service") as mock_svc_getter:
        mock_svc = mock_svc_getter.return_value
        mock_svc.list_comments_for_post = AsyncMock(return_value=[mock_comment])
        mock_svc.update_comment_status = AsyncMock(return_value=mock_comment)
        mock_svc.delete_comment = AsyncMock(return_value=None)

        db = ApiTestDbSession()
        client = api_client(admin_context=content_admin_context, db_session=db)

        # List comments
        res = client.get(f"/api/v1/admin/blog-posts/{post_id}/comments")
        assert res.status_code == 200
        comments = res.json()["data"]
        assert len(comments) == 1
        assert comments[0]["fullName"] == "Almaz"

        # Patch comment status
        patch_res = client.patch(
            f"/api/v1/admin/blog-posts/{post_id}/comments",
            json={"commentId": str(comment_id), "status": "approved"},
        )
        assert patch_res.status_code == 200

        # Delete comment
        del_res = client.request(
            "DELETE",
            f"/api/v1/admin/blog-posts/{post_id}/comments",
            json={"commentId": str(comment_id)},
        )
        assert del_res.status_code == 200
        assert del_res.json() == {"ok": True}


def test_banners_api(api_client, content_admin_context):
    banner = BannerDomain(
        id=1,
        banner_name="Grand Opening",
        image="https://cdn.example.com/banner.png",
        link="https://example.com/grand",
        active=True,
    )

    with patch("app.api.v1.routers.admin.content._get_content_service") as mock_svc_getter:
        mock_svc = mock_svc_getter.return_value
        mock_svc.list_banners = AsyncMock(return_value=[banner])
        mock_svc.create_banner = AsyncMock(return_value=banner)
        mock_svc.update_banner = AsyncMock(return_value=banner)
        mock_svc.delete_banner = AsyncMock(return_value=None)

        db = ApiTestDbSession()
        client = api_client(admin_context=content_admin_context, db_session=db)

        # List banners
        list_res = client.get("/api/v1/admin/banners")
        assert list_res.status_code == 200
        assert len(list_res.json()["data"]) == 1

        # Create banner
        create_res = client.post(
            "/api/v1/admin/banners",
            json={"bannerName": "Grand Opening", "image": "https://cdn.example.com/banner.png"},
        )
        assert create_res.status_code == 201

        # Patch banner
        patch_res = client.patch("/api/v1/admin/banners/1", json={"active": False})
        assert patch_res.status_code == 200

        # Delete banner
        del_res = client.delete("/api/v1/admin/banners/1")
        assert del_res.status_code == 200
        assert del_res.json() == {"ok": True}


def test_marketing_tracker_workspace_and_sheet_api(api_client, content_admin_context):
    sheet_id = uuid4()
    mock_ws = {
        "sheets": [MarketingSheetDomain(id=sheet_id, name="Leads", position=1)],
        "active_sheet_id": sheet_id,
        "columns": [
            MarketingColumnDomain(
                id=uuid4(), key="name", label="Name", column_type="text", position=1, is_system=True
            )
        ],
        "rows": [
            MarketingRowDomain(
                id=uuid4(), sheet_id=sheet_id, position=1, values={"name": "Kassahun"}
            )
        ],
    }

    with patch("app.api.v1.routers.admin.content._get_content_service") as mock_svc_getter:
        mock_svc = mock_svc_getter.return_value
        mock_svc.get_tracker_workspace = AsyncMock(return_value=mock_ws)
        mock_svc.create_tracker_sheet = AsyncMock(
            return_value=MarketingSheetDomain(id=uuid4(), name="Q2", position=2)
        )
        mock_svc.rename_tracker_sheet = AsyncMock(
            return_value=MarketingSheetDomain(id=sheet_id, name="Leads 2026", position=1)
        )
        mock_svc.delete_tracker_sheet = AsyncMock(return_value=None)

        db = ApiTestDbSession()
        client = api_client(admin_context=content_admin_context, db_session=db)

        # Get workspace
        ws_res = client.get("/api/v1/admin/marketing-tracker")
        assert ws_res.status_code == 200
        ws_data = ws_res.json()
        assert ws_data["activeSheetId"] == str(sheet_id)
        assert len(ws_data["sheets"]) == 1
        assert len(ws_data["columns"]) == 1
        assert len(ws_data["rows"]) == 1

        # Create sheet
        sheet_res = client.post(
            "/api/v1/admin/marketing-tracker/sheets", json={"name": "Q2"}
        )
        assert sheet_res.status_code == 201
        assert sheet_res.json()["name"] == "Q2"

        # Rename sheet
        rename_res = client.patch(
            f"/api/v1/admin/marketing-tracker/sheets/{sheet_id}",
            json={"name": "Leads 2026"},
        )
        assert rename_res.status_code == 200
        assert rename_res.json()["name"] == "Leads 2026"

        # Delete sheet
        del_res = client.delete(f"/api/v1/admin/marketing-tracker/sheets/{sheet_id}")
        assert del_res.status_code == 200
        assert del_res.json() == {"ok": True}
