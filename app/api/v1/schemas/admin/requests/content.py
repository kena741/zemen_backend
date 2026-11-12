"""Request schemas for Content, Blog, Banners, and Marketing Tracker."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateBlogPostRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str
    slug: str | None = None
    excerpt: str | None = None
    content_html: str = Field(alias="contentHtml")
    cover_image: str | None = Field(default=None, alias="coverImage")
    author_name: str | None = Field(default=None, alias="authorName")
    status: Literal["draft", "published", "archived"] = "draft"
    published_at: datetime | None = Field(default=None, alias="publishedAt")


class UpdateBlogPostRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID | None = None
    title: str | None = None
    slug: str | None = None
    excerpt: str | None = None
    content_html: str | None = Field(default=None, alias="contentHtml")
    cover_image: str | None = Field(default=None, alias="coverImage")
    author_name: str | None = Field(default=None, alias="authorName")
    status: Literal["draft", "published", "archived"] | None = None
    published_at: datetime | None = Field(default=None, alias="publishedAt")


class UpdateBlogCommentRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    comment_id: UUID = Field(alias="commentId")
    status: Literal["approved", "hidden", "pending"]


class DeleteBlogCommentRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    comment_id: UUID = Field(alias="commentId")


class CreateBannerRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    banner_name: str = Field(alias="bannerName")
    image: str
    link: str | None = None
    active: bool = True


class UpdateBannerRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int | None = None
    banner_name: str | None = Field(default=None, alias="bannerName")
    image: str | None = None
    link: str | None = None
    active: bool | None = None


class CreateTrackerSheetRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = "New Sheet"


class RenameTrackerSheetRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str


class AddTrackerColumnRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str
    label: str
    column_type: Literal["text", "yes-no", "boolean", "date"] = Field(
        default="text", alias="columnType"
    )


class AddTrackerRowRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sheet_id: UUID = Field(alias="sheetId")
    values: dict[str, Any] = Field(default_factory=dict)


class PatchTrackerRowRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    values: dict[str, Any]
